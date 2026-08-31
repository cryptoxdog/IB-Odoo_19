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
try:
    from constellation_node_sdk import GateClient, create_transport_packet  # type: ignore[no-redef]  # noqa: F811
except Exception as exc:  # pragma: no cover
    _SDK_IMPORT_ERROR = exc


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
    packet = create_transport_packet(
        action=action,
        payload=payload,
        tenant=tenant_ctx,
        source_node=local_node,
        destination_node="gate",
        reply_to=local_node,
        correlation_id=correlation_id,
        classification="internal",
        compliance_tags=compliance_tags,
        idempotency_key=idempotency_key,
        # `send_to_gate` bounds the real HTTP call with config.timeout_seconds;
        # `timeout_ms` is the budget advertised downstream. Deriving both from
        # one config value stops the header promising 30 s while this caller
        # actually waits for something else (the SDK default is a fixed 30000).
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
        # was blank. classify_transport_failure already reads the type name;
        # carrying it into the message keeps the durable record diagnosable
        # without changing classification.
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
