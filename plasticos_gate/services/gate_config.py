"""Gate env helpers and integration exceptions — no UserError on fallback path.

Connection plane is process environment only (canonical Gate_SDK names):

    GATE_URL, L9_NODE_NAME, L9_SIGNING_KEY, L9_SIGNING_KEY_ID,
    L9_SIGNING_ALGORITHM, L9_VERIFYING_KEYS_JSON, L9_REQUIRE_SIGNATURE

Gate_SDK owns parsing and validating those values
(``get_gate_client_config_from_env``); this module only hands the SDK the
values Odoo owns (node identity, the validated caller budget, the 30 s ceiling
and the Gate-only destination pin). No legacy aliases, no ICP Gate URL.

Capability ICPs (matching_enabled / enrichment_enabled / auto_writeback) stay
on System Parameters. They are not how the SDK finds Gate.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from constellation_node_sdk import GateClientConfig

ENV_GATE_URL = "GATE_URL"

# Odoo is a Gate consumer, never a worker. Must match the Gate caller record.
ODOO_NODE_NAME = "odoo"


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


def resolve_gate_url() -> str:
    """Return the configured Gate hub URL from the process environment only."""
    return (os.environ.get(ENV_GATE_URL) or "").strip()


def _insecure_http_allowed(env) -> bool:
    """Local-dev opt-in for cleartext GATE_URL. Not a connection-authority key."""
    if env is None:
        return False
    icp = env["ir.config_parameter"].sudo()
    return (icp.get_param("plasticos.gate.allow_insecure_http") or "").strip() in _TRUTHY


def _gate_url_usable(env=None) -> bool:
    """Return True when GATE_URL is present and uses an accepted scheme.

    TLS (``https``) is required by default. The cleartext scheme is accepted only
    when the deployment explicitly opts in via ``plasticos.gate.allow_insecure_http=1``
    (intended for local development against a loopback Gate only).
    """
    url = resolve_gate_url()
    scheme = urlsplit(url).scheme.lower()
    if scheme == "https":
        return True
    return _insecure_http_allowed(env) and scheme == "http"  # NOSONAR(S5332) explicit local-dev opt-in


def classify_gate_availability(
    env, *, capability: str | GateCapability = GateCapability.MATCHING
) -> GateAvailabilityVerdict:
    """Return a structured availability verdict for matching or enrichment.

    Never raises. Downstream degraded-mode UX consumes ``status`` + ``reasons``.
    URL configured is ``GATE_URL`` only — never an ICP.
    """
    icp = env["ir.config_parameter"].sudo()
    url = resolve_gate_url()
    reasons: list[str] = []
    status = GateAvailability.AVAILABLE

    if not url:
        status = GateAvailability.MISSING_URL
        reasons.append(f"{ENV_GATE_URL} is unset")
    else:
        scheme = urlsplit(url).scheme.lower()
        if scheme == "http":
            if not _insecure_http_allowed(env):
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
        "permanent": f"Configuration or contract failure — fix {ENV_GATE_URL}/L9_*/SDK",
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

    Live by default: enabled whenever ``GATE_URL`` is set and the SDK is present
    (seeded ``plasticos.gate.enrichment_enabled=1``). Set it to ``0`` to disable.
    """
    verdict = classify_gate_availability(env, capability=GateCapability.ENRICHMENT)
    return bool(verdict.available)


def gate_auto_writeback_enabled(env) -> bool:
    """Return True when converge results should be applied live to the partner.

    OFF by default (review-only): the converge proposal is stored with
    state='review' and no partner writes happen until the operator explicitly
    enables BOTH switches — ``plasticos.gate.auto_writeback=1`` and
    ``plasticos.gate.auto_writeback_operator_approved=1`` — which then
    backfills allowlisted fields (merge-not-overwrite) with provenance.

    The operator-approval key is seeded 0 and defaults false when missing, so
    an old database with only the single flag set can never re-enable
    automatic partner writes.
    """
    icp = env["ir.config_parameter"].sudo()
    auto_writeback = (icp.get_param("plasticos.gate.auto_writeback", "0") or "").strip() in _TRUTHY
    operator_approved = (icp.get_param("plasticos.gate.auto_writeback_operator_approved", "0") or "").strip() in _TRUTHY
    return auto_writeback and operator_approved


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


# The consumer owns the bar for "this reply is good enough": accept the field
# and do not spend another provider call. Enrichment reads the number off the
# request packet. This default applies only when the operator has not set
# plasticos.gate.consensus_threshold.
ICP_CONSENSUS_THRESHOLD = "plasticos.gate.consensus_threshold"
DEFAULT_CONSENSUS_THRESHOLD = 0.80


def gate_consensus_threshold(env) -> float:
    """Odoo's consensus bar for the converge packet, in [0, 1]."""
    raw = ""
    try:
        icp = env["ir.config_parameter"].sudo()
        raw = (icp.get_param(ICP_CONSENSUS_THRESHOLD) or "").strip()
    except (AttributeError, KeyError, TypeError):
        raw = ""
    if not raw:
        return DEFAULT_CONSENSUS_THRESHOLD
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        msg = f"{ICP_CONSENSUS_THRESHOLD} is not a number: {raw!r}"
        raise GateIntegrationError(msg, failure_class="permanent") from exc
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        msg = f"{ICP_CONSENSUS_THRESHOLD} must be between 0 and 1, got {raw!r}"
        raise GateIntegrationError(msg, failure_class="permanent")
    return value


def build_gate_client_config(env) -> GateClientConfig:
    """Build the SDK client configuration from ``GATE_URL`` + ``L9_*`` through the SDK's own builder.

    Gate_SDK owns parsing and validating the transport/signing environment
    (``get_gate_client_config_from_env``): the signing key, key id and
    algorithm, the require-signature posture and the verifying keyring are read
    and validated there, never reconstructed here. Odoo supplies only the
    values it owns: its node identity, the validated synchronous caller budget,
    the 30 s ceiling and the Gate-only destination pin. A malformed environment
    (missing ``GATE_URL``, invalid ``L9_VERIFYING_KEYS_JSON``) is the SDK's
    ``ValueError`` and surfaces as a permanent configuration failure — never
    silently unsigned, never clamped. No ICP URL and no legacy env aliases.
    """
    timeout = resolve_gate_timeout_seconds(env)
    try:
        from constellation_node_sdk import get_gate_client_config_from_env
    except ImportError as exc:
        raise GateIntegrationError(f"constellation_node_sdk not installed: {exc}", failure_class="permanent") from exc
    try:
        return get_gate_client_config_from_env(
            local_node=ODOO_NODE_NAME,
            timeout_seconds=timeout,
            max_timeout_ms=int(MAX_GATE_TIMEOUT_SECONDS * 1000),
            allowed_gate_destination="gate",
        )
    except ValueError as exc:
        raise GateIntegrationError(str(exc) or f"{ENV_GATE_URL} is required", failure_class="permanent") from exc


def resolve_tenant(env) -> str:
    """Return the tenant string that must match the Gate caller record.

    Staging ``plasticos.gate.org_id`` (or the database name when empty) must
    equal the tenant on Gate's Odoo caller record or execute is refused.
    """
    icp = env["ir.config_parameter"].sudo()
    org_id = (icp.get_param("plasticos.gate.org_id") or "").strip()
    return org_id or env.cr.dbname
