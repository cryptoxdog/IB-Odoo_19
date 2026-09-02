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
# bare dev environments may lack it). Bind the entry point as `Any` so the
# guard assignments below are type-safe under mypy.
GateClient: Any = None
_SDK_IMPORT_ERROR: Exception | None = None
# SDK-typed transport errors. `TransportError` is the root of the SDK's
# validation/integrity/authentication/authorization/expiry family — every one of
# them is a contract failure, never a transient.
_SDK_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = ()
try:
    from constellation_node_sdk import (  # type: ignore[no-redef]  # noqa: F811
        GateClient,
        TransportError,
    )

    _SDK_TRANSPORT_ERRORS = (TransportError,)
except Exception as exc:  # pragma: no cover
    _SDK_IMPORT_ERROR = exc

# httpx is a hard Gate_SDK dependency (`httpx>=0.27.0` in its pyproject).
# SDK-GAP-2 (the SDK leaking its HTTP library's exceptions instead of raising
# its own typed transport errors — see FINAL_FINDINGS.md) is CLOSED by the
# release that added `GateClient.execute`: it raises GateTimeoutError /
# GateConnectionError / GateHTTPError instead. These types are retained as
# defense in depth — they cost nothing, and they keep classification correct if
# any path ever surfaces a raw httpx error again. Naming types is how this
# bridge classifies a connection fault WITHOUT reading exception strings; it is
# not an Odoo HTTP client and issues no request.
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
    if GateClient is None:
        raise GateIntegrationError(
            f"constellation_node_sdk not installed: {_SDK_IMPORT_ERROR}",
            failure_class=TransportFailureClass.PERMANENT.value,
        )
    if not hasattr(GateClient, "execute"):
        # Fail closed and legibly rather than as an AttributeError deep in the
        # call: this bridge requires the SDK release that closed SDK-GAP-1.
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
    # Node identity has one owner: the config object the SDK reads source_node
    # and reply_to from. A second, independently-normalized read of the ICP
    # parameter here could drift from the identity actually on the wire.
    local_node = config.local_node
    tenant = resolve_tenant(env)
    user = env.user
    tenant_ctx = {
        "actor": tenant,
        "on_behalf_of": tenant,
        "originator": local_node,
        "org_id": tenant,
        "user_id": str(user.id) if user and user.id else None,
    }
    # SDK-GAP-1 CLOSED: Gate_SDK now exposes an application-facing
    # `GateClient.execute(action, payload, ...)`, so Odoo no longer builds a
    # TransportPacket. Every argument below is a business input Odoo
    # legitimately owns; the SDK owns the root packet, source and reply-to
    # identity (from GateClientConfig.local_node), signing, HTTP, and response
    # validation (pack ADR-007 — one SDK invocation surface).
    #
    # Transport POLICY stays the SDK's, as before:
    #   destination_node -> SDK forces "gate"; GateClientConfig
    #                       (allowed_gate_destination="gate") enforces it and
    #                       validate_outbound_gate_packet rejects anything else
    #                       (pack ADR-002 / ADR-016).
    #   classification   -> SDK default "internal".
    #   priority,        -> SDK defaults; Odoo has no basis to override them.
    #   retention_days
    try:
        response_packet = _run_async(
            client.execute(
                action=action,
                payload=payload,
                tenant=tenant_ctx,
                correlation_id=correlation_id,
                compliance_tags=compliance_tags,
                idempotency_key=idempotency_key,
                # SDK-GAP-3 CLOSED: `execute` writes this budget into the packet
                # header AND derives the network deadline from that same header,
                # so the advertised and actual budgets can no longer diverge.
                # Passing it explicitly keeps the caller's validated config the
                # single source of the budget (pack ADR-009).
                timeout_ms=int(float(config.timeout_seconds) * 1000),
            )
        )
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
