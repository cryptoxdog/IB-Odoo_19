"""Canonical Odoo -> Gate SDK bridge (sole constellation_node_sdk import site)."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from .gate_config import GateIntegrationError, build_gate_client_config, get_matching_action, resolve_tenant

# The SDK is optional at import time (Odoo.sh installs it via requirements.txt;
# bare dev environments may lack it). Bind the two entry points as `Any` so the
# guard assignments below are type-safe under mypy.
GateClient: Any = None
create_transport_packet: Any = None
_SDK_IMPORT_ERROR: Exception | None = None
try:
    from constellation_node_sdk import GateClient, create_transport_packet  # noqa: F811
except Exception as exc:  # pragma: no cover
    _SDK_IMPORT_ERROR = exc


def _require_sdk() -> None:
    if GateClient is None or create_transport_packet is None:
        raise GateIntegrationError(f"constellation_node_sdk not installed: {_SDK_IMPORT_ERROR}")


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
    )
    try:
        response_packet = _run_async(client.send_to_gate(packet))
    except Exception as exc:
        raise GateIntegrationError(str(exc)) from exc
    return {
        "packet": response_packet,
        "payload": dict(response_packet.payload),
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
