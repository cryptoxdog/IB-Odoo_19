"""Canonical Odoo -> Gate SDK bridge (sole constellation_node_sdk import site)."""

from __future__ import annotations

import asyncio
import logging
import threading
from enum import StrEnum
from typing import Any

from .gate_config import (
    GateIntegrationError,
    build_gate_client_config,
    get_enrichment_action,
    get_matching_action,
    resolve_tenant,
)

_logger = logging.getLogger(__name__)

# The SDK is optional at import time (Odoo.sh installs it via requirements.txt;
# bare dev environments may lack it). Bind the entry point as `Any` so the
# guard assignments below are type-safe under mypy.
GateClient: Any = None
_SDK_IMPORT_ERROR: Exception | None = None
try:
    from constellation_node_sdk import GateClient  # type: ignore[no-redef]  # noqa: F811
except Exception as exc:  # pragma: no cover
    _SDK_IMPORT_ERROR = exc

# Typed transport failures, feature-detected on purpose: an SDK predating the
# taxonomy leaves these tuples empty and classification falls back to the token
# classifier below. That fallback is precisely why the token classifier stays —
# it also still covers non-SDK exceptions (httpx, asyncio) that reach us raw.
_RETRYABLE_SDK_ERRORS: tuple[type[BaseException], ...] = ()
_PERMANENT_SDK_ERRORS: tuple[type[BaseException], ...] = ()
_GateHTTPError: Any = None
try:
    from constellation_node_sdk import (
        GateConfigurationError,
        GateConnectionError,
        GateHTTPError,
        GatePolicyError,
        GateResponseError,
        GateSecurityError,
        GateTimeoutError,
    )

    _RETRYABLE_SDK_ERRORS = (GateTimeoutError, GateConnectionError)
    _PERMANENT_SDK_ERRORS = (
        GateConfigurationError,
        GatePolicyError,
        GateResponseError,
        GateSecurityError,
    )
    _GateHTTPError = GateHTTPError
except Exception as exc:  # pragma: no cover - SDK without the typed taxonomy
    _logger.debug("constellation_node_sdk typed error taxonomy unavailable: %s", exc)


class TransportFailureClass(StrEnum):
    """Operator-visible transport failure categories (no silent local substitution)."""

    RETRYABLE = "retryable"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


_RETRYABLE_TOKENS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "connection reset",
    "connection refused",
    "connection aborted",
    "broken pipe",
    "network unreachable",
    "503",
    "502",
    "504",
    "429",
    "gateway",
)
_PERMANENT_TOKENS = (
    "unauthorized",
    "forbidden",
    "401",
    "403",
    "404",
    "invalid signature",
    "validation",
    "schema",
    "not installed",
    "destination",
    "policy",
)


def classify_transport_failure(exc: BaseException) -> TransportFailureClass:
    """Classify a transport exception as retryable, permanent, or unknown."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(token in text for token in _PERMANENT_TOKENS):
        return TransportFailureClass.PERMANENT
    if any(token in text for token in _RETRYABLE_TOKENS):
        return TransportFailureClass.RETRYABLE
    if isinstance(exc, (TimeoutError, ConnectionError, asyncio.TimeoutError)):
        return TransportFailureClass.RETRYABLE
    return TransportFailureClass.UNKNOWN


def classify_gate_failure(exc: BaseException) -> TransportFailureClass:
    """Classify a Gate failure: SDK typed errors first, token heuristics second.

    The SDK owns the transport, so it knows what failed better than any string
    match can. `classify_transport_failure` stays as the fallback for two live
    cases: an SDK predating the typed taxonomy, and non-SDK exceptions that
    reach us raw (httpx, asyncio) before the SDK can wrap them.
    """
    if _RETRYABLE_SDK_ERRORS and isinstance(exc, _RETRYABLE_SDK_ERRORS):
        return TransportFailureClass.RETRYABLE
    if _GateHTTPError is not None and isinstance(exc, _GateHTTPError):
        # `is_client_error` / `is_server_error` are properties, not methods.
        if exc.is_server_error:
            return TransportFailureClass.RETRYABLE
        if exc.is_client_error:
            return TransportFailureClass.PERMANENT
        return TransportFailureClass.UNKNOWN
    if _PERMANENT_SDK_ERRORS and isinstance(exc, _PERMANENT_SDK_ERRORS):
        return TransportFailureClass.PERMANENT
    return classify_transport_failure(exc)


def _require_sdk() -> None:
    if GateClient is None:
        raise GateIntegrationError(
            f"constellation_node_sdk not installed: {_SDK_IMPORT_ERROR}",
            failure_class=TransportFailureClass.PERMANENT.value,
        )
    if not hasattr(GateClient, "execute"):
        # Fail closed and legibly rather than as an AttributeError deep in the
        # call: this bridge requires the SDK release where GateClient owns
        # TransportPacket construction.
        raise GateIntegrationError(
            "constellation_node_sdk is too old: GateClient.execute() is required "
            "(the SDK owns TransportPacket construction). Bump the "
            "constellation-node-sdk pin in requirements.txt.",
            failure_class=TransportFailureClass.PERMANENT.value,
        )


def _run_async(coro):
    """Bridge async GateClient.execute for synchronous Odoo workers."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict[str, Any] = {}
    err: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            box["result"] = asyncio.run(coro)
        except BaseException as exc:  # pragma: no cover
            err["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in err:
        raise err["error"]
    return box.get("result")


def send_action(
    env,
    *,
    action: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    compliance_tags: tuple[str, ...] = (),
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Execute one action through Gate and return response packet + payload dicts.

    Odoo supplies business inputs only. The SDK builds and owns the
    TransportPacket; this bridge never constructs one.
    """
    _require_sdk()
    config = build_gate_client_config(env)
    client = GateClient(config)
    icp = env["ir.config_parameter"].sudo()
    local_node = (icp.get_param("plasticos.gate.local_node") or "odoo").strip().lower()
    tenant = resolve_tenant(env)
    user = env.user
    tenant_ctx = {
        "actor": tenant,
        "on_behalf_of": tenant,
        "originator": local_node,
        "org_id": tenant,
        "user_id": str(user.id) if user and user.id else None,
    }
    try:
        # Odoo names the intent and hands over the domain payload; the SDK owns
        # every transport mechanic — root packet, Gate destination, source and
        # reply-to identity (from config.local_node), deadline translation,
        # signing, HTTP, and response validation. Odoo never names a destination.
        response_packet = _run_async(
            client.execute(
                action=action,
                payload=payload,
                tenant=tenant_ctx,
                correlation_id=correlation_id,
                classification="internal",
                compliance_tags=compliance_tags,
                idempotency_key=idempotency_key,
                # One validated budget, one config object: `execute` writes this
                # into the packet header AND derives the network deadline from
                # that same header, so advertised and actual cannot diverge.
                timeout_ms=int(float(config.timeout_seconds) * 1000),
            )
        )
    except Exception as exc:
        failure = classify_gate_failure(exc)
        # Timeout exceptions stringify to nothing: measured against a real Gate
        # transport, an exhausted caller budget raises httpx `ConnectTimeout`
        # with `str(exc) == ""` (asyncio.TimeoutError and builtin TimeoutError
        # behave the same). A timeout is the most likely real Gate failure and
        # the caller budget makes it an expected outcome, yet the operator saw
        # "Gate enrichment failed (retryable): " and the run stored
        # validation_issues=[""] — the classification was right and the reason
        # was blank. classify_gate_failure already reads the type name (via the
        # typed taxonomy, or the token fallback); carrying it into the message
        # keeps the durable record diagnosable without changing classification.
        detail = str(exc) or type(exc).__name__
        raise GateIntegrationError(detail, failure_class=failure.value) from exc
    packet_k, payload_k, failure_k = "packet", "payload", "failure_class"
    return {
        packet_k: response_packet,
        payload_k: dict(response_packet.payload),
        failure_k: None,
    }


def send_match_action(
    env,
    *,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    action = get_matching_action(env)
    return send_action(
        env,
        action=action,
        payload=payload,
        correlation_id=correlation_id,
        compliance_tags=("ERP", "MATCHING"),
    )


def send_converge_action(
    env,
    *,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    action = get_enrichment_action(env)
    return send_action(
        env,
        action=action,
        payload=payload,
        correlation_id=correlation_id,
        compliance_tags=("ERP", "ENRICHMENT"),
        idempotency_key=idempotency_key,
    )
