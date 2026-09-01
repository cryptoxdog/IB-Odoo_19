"""Canonical Odoo -> Gate SDK bridge (sole constellation_node_sdk import site)."""

from __future__ import annotations

import asyncio
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

# The SDK is optional at import time (Odoo.sh installs it via requirements.txt;
# bare dev environments may lack it). Bind the two entry points as `Any` so the
# guard assignments below are type-safe under mypy.
GateClient: Any = None
create_transport_packet: Any = None
_SDK_IMPORT_ERROR: Exception | None = None
# SDK-typed transport errors. `TransportError` is the root of the SDK's
# validation/integrity/authentication/authorization/expiry family — every one of
# them is a contract failure, never a transient.
_SDK_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = ()
try:
    from constellation_node_sdk import (  # type: ignore[no-redef]  # noqa: F811
        GateClient,
        TransportError,
        create_transport_packet,
    )

    _SDK_TRANSPORT_ERRORS = (TransportError,)
except Exception as exc:  # pragma: no cover
    _SDK_IMPORT_ERROR = exc

# httpx is a hard Gate_SDK dependency (`httpx>=0.27.0` in its pyproject), and
# `GateClient.send_to_gate` propagates httpx exceptions to its caller unwrapped.
# Naming those types is how this bridge classifies a connection fault WITHOUT
# reading exception strings; it is not an Odoo HTTP client and issues no
# request. That the SDK leaks its HTTP library's exceptions instead of raising
# its own typed transport errors is recorded as a Gate_SDK capability gap
# (SDK-GAP-2) — see FINAL_FINDINGS.md.
_HTTP_TRANSIENT_ERRORS: tuple[type[BaseException], ...] = ()
_HTTP_CONFIG_ERRORS: tuple[type[BaseException], ...] = ()
_HTTPX_IMPORT_ERROR: Exception | None = None
try:
    import httpx

    _HTTP_TRANSIENT_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError)
    _HTTP_CONFIG_ERRORS = (httpx.UnsupportedProtocol, httpx.ProxyError, httpx.InvalidURL)
except Exception as exc:  # pragma: no cover
    # Absent only when the SDK itself is absent (httpx is an SDK dependency).
    # Classification then falls back to SDK/stdlib types; it never fails closed
    # on an import, because `_require_sdk` already refuses the send.
    _HTTPX_IMPORT_ERROR = exc


class TransportFailureClass(StrEnum):
    """Operator-visible transport failure categories (no silent local substitution)."""

    RETRYABLE = "retryable"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


# 408/429 are the two 4xx codes that mean "come back later" rather than "your
# request is wrong". 501 (not implemented) and 505 (version not supported) are
# 5xx codes that will not change on a retry.
_RETRYABLE_STATUS = frozenset({408, 429})
_PERMANENT_5XX_STATUS = frozenset({501, 505})


def _http_status(exc: BaseException) -> int | None:
    """Read an HTTP status off an exception that carries a response, if any.

    Duck-typed rather than keyed to one library: any exception exposing
    ``.response.status_code`` is classified by that status.
    """
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status if isinstance(status, int) else None


def classify_transport_failure(exc: BaseException) -> TransportFailureClass:
    """Classify a transport exception into an Odoo operator-visible category.

    Classification is **structural** — HTTP status codes and exception types —
    never substring matching on the exception message. Odoo owns the mapping
    from transport failure to its own UI/retry-advice categories (contract
    ADR-003); it does not own, and must not re-derive, transport truth. An
    earlier implementation scanned ``str(exc)`` for tokens like "502" and
    "timeout", which misclassified any message that merely mentioned one and
    silently failed for exceptions that stringify to empty (httpx timeouts do).
    """
    status = _http_status(exc)
    if status is not None:
        if status in _RETRYABLE_STATUS:
            return TransportFailureClass.RETRYABLE
        if 500 <= status <= 599 and status not in _PERMANENT_5XX_STATUS:
            return TransportFailureClass.RETRYABLE
        return TransportFailureClass.PERMANENT

    # Misconfigured endpoint/proxy/scheme: retrying cannot fix it.
    if _HTTP_CONFIG_ERRORS and isinstance(exc, _HTTP_CONFIG_ERRORS):
        return TransportFailureClass.PERMANENT

    # SDK contract failures (validation, integrity, signature, authorization,
    # expiry) are permanent by construction.
    if _SDK_TRANSPORT_ERRORS and isinstance(exc, _SDK_TRANSPORT_ERRORS):
        return TransportFailureClass.PERMANENT

    if isinstance(exc, (*_HTTP_TRANSIENT_ERRORS, TimeoutError, ConnectionError)):
        return TransportFailureClass.RETRYABLE

    # Gate policy violations raised before the send (`validate_outbound_gate_packet`
    # raises bare ValueError) and malformed canonical responses (pydantic
    # ValidationError subclasses ValueError) are both contract failures.
    if isinstance(exc, ValueError):
        return TransportFailureClass.PERMANENT

    return TransportFailureClass.UNKNOWN


def _require_sdk() -> None:
    if GateClient is None or create_transport_packet is None:
        raise GateIntegrationError(
            f"constellation_node_sdk not installed: {_SDK_IMPORT_ERROR}",
            failure_class=TransportFailureClass.PERMANENT.value,
        )


def _run_async(coro):
    """Bridge async GateClient.send_to_gate for synchronous Odoo workers."""
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
    """Send a TransportPacket to Gate and return packet + payload dicts."""
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
    # SDK-GAP-1: Gate_SDK exposes no application-facing execute(action, payload,
    # operation_id, timeout) — `GateClient.send_to_gate` requires a caller-built
    # packet — so this call cannot be deleted from Odoo. It is held to the
    # minimum the SDK forces: every argument below is either a business input
    # Odoo legitimately owns (action, payload, tenant, correlation, compliance
    # tags, operation identity) or local node identity read from Odoo config.
    #
    # Transport POLICY is left to the SDK deliberately:
    #   destination_node -> SDK default "gate"; GateClientConfig
    #                       (allowed_gate_destination="gate") enforces it and
    #                       validate_outbound_gate_packet rejects anything else,
    #                       so Odoo naming the destination was redundant routing
    #                       policy in domain code (pack ADR-002 / ADR-016).
    #   classification   -> SDK default "internal".
    #   priority,        -> SDK defaults; Odoo has no basis to override them.
    #   retention_days
    packet = create_transport_packet(
        action=action,
        payload=payload,
        tenant=tenant_ctx,
        source_node=local_node,
        reply_to=local_node,
        correlation_id=correlation_id,
        compliance_tags=compliance_tags,
        idempotency_key=idempotency_key,
        # SDK-GAP-3: the SDK does not derive the packet's advertised budget from
        # GateClientConfig.timeout_seconds (it hardcodes 30000), so the caller
        # must restate it or the header promises a budget this caller does not
        # honour. Both values come from the one validated config object, which
        # is what keeps them from drifting (pack ADR-009).
        timeout_ms=int(float(config.timeout_seconds) * 1000),
    )
    try:
        response_packet = _run_async(client.send_to_gate(packet))
    except Exception as exc:
        failure = classify_transport_failure(exc)
        # Timeout exceptions stringify to nothing: measured against a real Gate
        # transport, an exhausted caller budget raises httpx `ConnectTimeout`
        # with `str(exc) == ""` (asyncio.TimeoutError and builtin TimeoutError
        # behave the same). A timeout is the most likely real Gate failure and
        # the caller budget makes it an expected outcome, yet the operator saw
        # "Gate enrichment failed (retryable): " and the run stored
        # validation_issues=[""] — the classification was right and the reason
        # was blank. Naming the exception type keeps the durable record
        # diagnosable; a blank operator-visible reason is not a usable failure
        # state (pack ADR-015).
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
