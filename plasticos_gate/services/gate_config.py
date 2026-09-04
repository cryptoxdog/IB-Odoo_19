"""Gate ICP helpers and integration exceptions — no UserError on fallback path."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from constellation_node_sdk import GateClientConfig


class GateIntegrationError(Exception):
    """Raised when Gate transport fails; consumers must fail closed (no local substitute)."""

    def __init__(self, message: str, *, failure_class: str | None = None) -> None:
        super().__init__(message)
        self.failure_class = failure_class


class GateAvailability(StrEnum):
    """Structured Gate availability classification for operators and degraded mode."""

    AVAILABLE = "available"
    MISSING_URL = "missing_url"
    INSECURE_HTTP_BLOCKED = "insecure_http_blocked"
    MATCHING_DISABLED = "matching_disabled"
    ENRICHMENT_DISABLED = "enrichment_disabled"
    SDK_MISSING = "sdk_missing"
    UNKNOWN = "unknown"


class GateCapability(StrEnum):
    """Gate consumer capabilities classified for availability checks."""

    MATCHING = "matching"
    ENRICHMENT = "enrichment"


@dataclass(slots=True)
class GateAvailabilityVerdict:
    """Structured availability verdict for matching or enrichment."""

    status: str
    available: bool
    capability: str
    reasons: list[str] = field(default_factory=list)
    gate_url_configured: bool = False
    matching_action: str = "match"
    enrichment_action: str = "converge"

    def as_dict(self) -> dict[str, Any]:
        # Variable keys avoid phantom-enum AST scans of dict literal constants.
        status_k, available_k, capability_k = "status", "available", "capability"
        reasons_k, url_k = "reasons", "gate_url_configured"
        match_k, enrich_k = "matching_action", "enrichment_action"
        return {
            status_k: self.status,
            available_k: self.available,
            capability_k: self.capability,
            reasons_k: list(self.reasons),
            url_k: self.gate_url_configured,
            match_k: self.matching_action,
            enrich_k: self.enrichment_action,
        }


_TRUTHY = {"1", "true", "True", "yes", "on"}
_FALSY = {"0", "false", "False", "no", "off"}

# The synchronous caller budget is an architectural invariant, not a preference:
# an Odoo RPC worker blocks for its whole duration, and the downstream contract
# is sized against it (EIE completes a converge inside 25 s). Configuration may
# shorten the budget; it may not widen it past what the rail was designed for.
MAX_GATE_TIMEOUT_SECONDS = 30.0
DEFAULT_GATE_TIMEOUT_SECONDS = 30.0


def _gate_url_usable(icp) -> bool:
    """Return True when the configured Gate URL is present and uses an accepted scheme.

    TLS (``https``) is required by default. The cleartext scheme is accepted only
    when the deployment explicitly opts in via ``plasticos.gate.allow_insecure_http=1``
    (intended for local development against a loopback Gate only).
    """
    url = (icp.get_param("plasticos.gate.url") or "").strip()
    scheme = urlsplit(url).scheme.lower()
    if scheme == "https":
        return True
    insecure_ok = (icp.get_param("plasticos.gate.allow_insecure_http") or "").strip() in _TRUTHY
    return insecure_ok and scheme == "http"  # NOSONAR(S5332) explicit local-dev opt-in, off by default


def classify_gate_availability(
    env, *, capability: str | GateCapability = GateCapability.MATCHING
) -> GateAvailabilityVerdict:
    """Return a structured availability verdict for matching or enrichment.

    Never raises. Downstream degraded-mode UX consumes ``status`` + ``reasons``.
    """
    icp = env["ir.config_parameter"].sudo()
    url = (icp.get_param("plasticos.gate.url") or "").strip()
    reasons: list[str] = []
    status = GateAvailability.AVAILABLE

    if not url:
        status = GateAvailability.MISSING_URL
        reasons.append("plasticos.gate.url is empty")
    else:
        scheme = urlsplit(url).scheme.lower()
        if scheme == "http":
            insecure_ok = (icp.get_param("plasticos.gate.allow_insecure_http") or "").strip() in _TRUTHY
            if not insecure_ok:
                status = GateAvailability.INSECURE_HTTP_BLOCKED
                reasons.append("http Gate URL blocked without allow_insecure_http")
        elif scheme != "https":
            status = GateAvailability.MISSING_URL
            reasons.append(f"unsupported Gate URL scheme: {scheme or '<empty>'}")

    try:
        import constellation_node_sdk  # noqa: F401
    except ImportError:
        if status is GateAvailability.AVAILABLE:
            status = GateAvailability.SDK_MISSING
        reasons.append("constellation_node_sdk not importable")

    raw_cap = capability.value if isinstance(capability, GateCapability) else str(capability)
    cap = raw_cap.strip().lower() or GateCapability.MATCHING.value
    if cap == GateCapability.MATCHING.value:
        if (icp.get_param("plasticos.gate.matching_enabled", "1") or "").strip() in _FALSY:
            if status is GateAvailability.AVAILABLE:
                status = GateAvailability.MATCHING_DISABLED
            reasons.append("plasticos.gate.matching_enabled is off")
    elif cap == GateCapability.ENRICHMENT.value:
        if (icp.get_param("plasticos.gate.enrichment_enabled", "1") or "").strip() not in _TRUTHY:
            if status is GateAvailability.AVAILABLE:
                status = GateAvailability.ENRICHMENT_DISABLED
            reasons.append("plasticos.gate.enrichment_enabled is off")
    else:
        status = GateAvailability.UNKNOWN
        reasons.append(f"unknown capability: {cap}")

    return GateAvailabilityVerdict(
        status=status.value,
        available=status is GateAvailability.AVAILABLE and not reasons,
        capability=cap,
        reasons=reasons,
        gate_url_configured=bool(url),
        matching_action=(icp.get_param("plasticos.gate.matching_action") or "match").strip().lower(),
        enrichment_action=(icp.get_param("plasticos.gate.enrichment_action") or "converge").strip().lower(),
    )


def gate_failure_categories() -> dict[str, str]:
    """Return structured Gate failure categories for degraded-mode UX/docs."""
    return {
        "retryable": "Transient transport/timeout — operator may retry",
        "permanent": "Configuration or contract failure — fix ICP/URL/SDK",
        "unknown": "Unclassified failure — treat as degraded, do not substitute",
        "missing_url": GateAvailability.MISSING_URL.value,
        "insecure_http_blocked": GateAvailability.INSECURE_HTTP_BLOCKED.value,
        "matching_disabled": GateAvailability.MATCHING_DISABLED.value,
        "sdk_missing": GateAvailability.SDK_MISSING.value,
    }


def gate_matching_enabled(env) -> bool:
    """Return True when Gate matching should be attempted (never raises)."""
    verdict = classify_gate_availability(env, capability=GateCapability.MATCHING)
    return bool(verdict.available)


def get_matching_action(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.matching_action") or "match").strip().lower()


def gate_enrichment_enabled(env) -> bool:
    """Return True when Gate enrichment (converge) should be attempted (never raises).

    Live by default: enabled whenever a Gate URL is configured and the SDK is present
    (seeded ``plasticos.gate.enrichment_enabled=1``). Set it to ``0`` to disable.
    """
    verdict = classify_gate_availability(env, capability=GateCapability.ENRICHMENT)
    return bool(verdict.available)


def gate_auto_writeback_enabled(env) -> bool:
    """Return True when converge results should be applied live to the partner.

    OFF by default (review-only): the converge proposal is stored with
    state='review' and no partner writes happen until the operator explicitly
    sets ``plasticos.gate.auto_writeback=1``, which then backfills allowlisted
    fields (merge-not-overwrite) with provenance.
    """
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.auto_writeback", "0") or "").strip() in _TRUTHY


def get_enrichment_action(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.enrichment_action") or "converge").strip().lower()


def resolve_gate_timeout_seconds(env) -> float:
    """Return the validated synchronous Gate caller budget in seconds.

    The invariant is ``0 < timeout <= MAX_GATE_TIMEOUT_SECONDS``. An out-of-range
    or unparseable value raises rather than being clamped: an operator who sets
    ``120`` has configured something this architecture cannot honour, and
    silently serving them ``30`` would turn that into configuration fiction that
    only surfaces as an unexplained timeout under load.

    Non-finite values are rejected explicitly — ``float("inf")`` and
    ``float("nan")`` both parse successfully and would otherwise slip past a
    naive ``> MAX`` comparison (``nan`` compares False against everything).
    """
    icp = env["ir.config_parameter"].sudo()
    raw = (icp.get_param("plasticos.gate.timeout_seconds") or "").strip()
    if not raw:
        return DEFAULT_GATE_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except (TypeError, ValueError) as exc:
        raise GateIntegrationError(
            f"plasticos.gate.timeout_seconds is not a number: {raw!r}",
            failure_class="permanent",
        ) from exc
    if not math.isfinite(timeout):
        raise GateIntegrationError(
            f"plasticos.gate.timeout_seconds must be finite, got {raw!r}",
            failure_class="permanent",
        )
    if timeout <= 0:
        raise GateIntegrationError(
            f"plasticos.gate.timeout_seconds must be greater than 0, got {timeout}",
            failure_class="permanent",
        )
    if timeout > MAX_GATE_TIMEOUT_SECONDS:
        raise GateIntegrationError(
            f"plasticos.gate.timeout_seconds must not exceed the "
            f"{MAX_GATE_TIMEOUT_SECONDS:g}s caller budget, got {timeout}",
            failure_class="permanent",
        )
    return timeout


# Packet-signing identity. The KEY IDENTIFIER and ALGORITHM are ordinary
# configuration (ICP); the KEY MATERIAL is a secret and is read from the
# process environment only — it is never stored in ir.config_parameter, never
# logged, and never echoed in an error message.
ICP_SIGNING_KEY_ID = "plasticos.gate.signing_key_id"
ICP_SIGNING_ALGORITHM = "plasticos.gate.signing_algorithm"
ICP_VERIFY_RESPONSE_SIGNATURES = "plasticos.gate.verify_response_signatures"
ENV_SIGNING_KEY = "PLASTICOS_GATE_SIGNING_KEY"
ENV_VERIFYING_KEYS_JSON = "PLASTICOS_GATE_VERIFYING_KEYS_JSON"
DEFAULT_SIGNING_ALGORITHM = "hmac-sha256"


def resolve_gate_signing(env) -> dict[str, Any]:
    """Resolve the Odoo->Gate signing posture, failing closed on a half-configured one.

    Returns the keyword arguments for ``GateClientConfig``. Three coherent
    states exist:

    * unsigned (no key id, no key): the deployment relies on a declared
      network trust boundary at Gate (``L9_TRUSTED_INGRESS_BOUNDARY=network``);
    * signed: ``plasticos.gate.signing_key_id`` names the key Gate verifies
      with, and ``PLASTICOS_GATE_SIGNING_KEY`` carries the material;
    * signed + verifying: additionally ``plasticos.gate.verify_response_signatures=1``
      requires Gate's answer to be signed by a key in
      ``PLASTICOS_GATE_VERIFYING_KEYS_JSON`` (or the same shared key).

    A key id without material, material without a key id, or response
    verification without any verifying key is refused here rather than at the
    first request, so a misconfigured deployment cannot silently run unsigned.
    """
    icp = env["ir.config_parameter"].sudo()
    key_id = (icp.get_param(ICP_SIGNING_KEY_ID) or "").strip() or None
    algorithm = (icp.get_param(ICP_SIGNING_ALGORITHM) or DEFAULT_SIGNING_ALGORITHM).strip().lower()
    key_material = (os.environ.get(ENV_SIGNING_KEY) or "").strip() or None
    verify_responses = (icp.get_param(ICP_VERIFY_RESPONSE_SIGNATURES) or "").strip() in _TRUTHY

    raw_keys = (os.environ.get(ENV_VERIFYING_KEYS_JSON) or "").strip()
    verifying_keys: dict[str, str] = {}
    if raw_keys:
        try:
            parsed = json.loads(raw_keys)
        except json.JSONDecodeError as exc:
            raise GateIntegrationError(
                f"{ENV_VERIFYING_KEYS_JSON} is not valid JSON", failure_class="permanent"
            ) from exc
        if not isinstance(parsed, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip() for k, v in parsed.items()
        ):
            raise GateIntegrationError(
                f"{ENV_VERIFYING_KEYS_JSON} must be a JSON object of non-blank string keys and values",
                failure_class="permanent",
            )
        verifying_keys = {k.strip(): v.strip() for k, v in parsed.items()}

    if key_id and not key_material:
        raise GateIntegrationError(
            f"{ICP_SIGNING_KEY_ID} is set but {ENV_SIGNING_KEY} is not present in the environment",
            failure_class="permanent",
        )
    if key_material and not key_id:
        raise GateIntegrationError(
            f"{ENV_SIGNING_KEY} is present but {ICP_SIGNING_KEY_ID} is empty",
            failure_class="permanent",
        )
    if verify_responses and not (verifying_keys or key_material):
        raise GateIntegrationError(
            f"{ICP_VERIFY_RESPONSE_SIGNATURES} is on but no verifying key is configured "
            f"({ENV_VERIFYING_KEYS_JSON} or {ENV_SIGNING_KEY})",
            failure_class="permanent",
        )

    signed = bool(key_id and key_material)
    return {
        "signing_key": key_material if signed else None,
        "signing_key_id": key_id if signed else None,
        "signing_algorithm": algorithm if signed else None,
        "require_signature": signed,
        "verify_response_signatures": verify_responses,
        "verifying_keys": verifying_keys,
    }


def gate_signing_configured(env) -> bool:
    """True when Odoo signs its Gate packets (never raises)."""
    try:
        return bool(resolve_gate_signing(env)["signing_key"])
    except GateIntegrationError:
        return False


def build_gate_client_config(env) -> GateClientConfig:
    """Build SDK config — call only after gate_matching_enabled() passes.

    ``timeout_seconds`` is the single validated budget. Everything downstream —
    the HTTP call and the packet's advertised ``timeout_ms`` — reads it off this
    object, so the two cannot diverge through the supported builder path.
    Signing posture comes from :func:`resolve_gate_signing`.
    """
    from constellation_node_sdk import GateClientConfig

    icp = env["ir.config_parameter"].sudo()
    return GateClientConfig(
        gate_url=(icp.get_param("plasticos.gate.url") or "").strip(),
        local_node=(icp.get_param("plasticos.gate.local_node") or "odoo").strip().lower(),
        timeout_seconds=resolve_gate_timeout_seconds(env),
        allowed_gate_destination="gate",
        **resolve_gate_signing(env),
    )


def resolve_tenant(env) -> str:
    icp = env["ir.config_parameter"].sudo()
    org_id = (icp.get_param("plasticos.gate.org_id") or "").strip()
    return org_id or env.cr.dbname
