"""Canonical Odoo -> Gate SDK bridge (sole constellation_node_sdk import site).

Ownership at this boundary (ADR-003-single; gate-integration ADR-001/003/007):

* Gate_SDK owns transport: packet construction, signing, HTTP, response
  validation, the typed error taxonomy and its retryability verdict
  (``GateClientError.retryable``), transport/signing environment parsing, and
  the consumer admission probe (``GateClient.activate``).
* Constellation.Gate owns authorization: Odoo asks, Gate answers.
* Odoo owns domain intent (action + payload), the tenant, the synchronous
  caller budget, the logical operation identity, and what a retryable or
  permanent failure means to an operator (``TransportFailureClass`` -> durable
  run state).

This module therefore never imports ``httpx``, never reads an HTTP status, and
never re-derives retryability from an exception type or message.
"""

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

# Odoo caller-policy record: match + converge only. Never request sync.
_ODOO_REQUIRED_ACTIONS: tuple[str, ...] = ("match", "converge")

# The SDK is optional at import time (Odoo.sh installs it via requirements.txt;
# bare dev environments may lack it). Bind the entry point as `Any` so the
# guard assignments below are type-safe under mypy. `_require_sdk` refuses the
# send when the SDK is absent or predates the Gate_SDK 1.2 surface this bridge
# is written against (`GateClient.execute` / `activate`, `GateClientError`).
GateClient: Any = None
_SDK_IMPORT_ERROR: Exception | None = None
# Root of the SDK's typed client failures. Every failure that leaves the Gate
# client surface is one of these and carries its own `.retryable` verdict.
_SDK_CLIENT_ERRORS: tuple[type[BaseException], ...] = ()
# Gate refused the caller's authority: the admission receipt for that identity
# can no longer be trusted and is dropped (see `_forget_admission`).
_SDK_AUTHORIZATION_ERRORS: tuple[type[BaseException], ...] = ()
try:
    from constellation_node_sdk import (  # type: ignore[no-redef]  # noqa: F811
        GateAuthorizationError,
        GateClient,
        GateClientError,
    )

    _SDK_CLIENT_ERRORS = (GateClientError,)
    _SDK_AUTHORIZATION_ERRORS = (GateAuthorizationError,)
except Exception as exc:  # pragma: no cover
    _SDK_IMPORT_ERROR = exc


class TransportFailureClass(StrEnum):
    """Odoo-owned durable failure categories (operator-visible; no silent local substitution).

    ``RETRYABLE`` and ``PERMANENT`` are projections of the SDK's ``retryable``
    verdict. ``UNKNOWN`` is reserved for exceptions that are not Gate transport
    outcomes at all (an unexpected programming error reaching the boundary);
    the downstream persistence shells record those as ``degraded``.
    """

    RETRYABLE = "retryable"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


def failure_class_for(exc: BaseException) -> TransportFailureClass | None:
    """Project an SDK transport failure onto Odoo's durable category.

    The SDK owns whether a failure is retryable (``GateClientError.retryable``:
    Gate unreachable or the deadline elapsed -> ``True``; authorization,
    configuration, security, policy and non-canonical responses -> ``False``).
    Odoo owns only what that verdict means to an operator. Returns ``None`` for
    anything that is not an SDK client error: such an exception is not a Gate
    transport outcome and stays subject to the caller's generic failure
    handling instead of being labelled retryable or permanent here.
    """
    if _SDK_CLIENT_ERRORS and isinstance(exc, _SDK_CLIENT_ERRORS):
        # The isinstance guard proves `exc` is a GateClientError, which defines
        # `.retryable`; mypy cannot narrow through the runtime-bound tuple.
        retryable: bool = exc.retryable  # type: ignore[attr-defined]
        return TransportFailureClass.RETRYABLE if retryable else TransportFailureClass.PERMANENT
    return None


def _require_sdk() -> None:
    if GateClient is None:
        raise GateIntegrationError(
            f"constellation_node_sdk not installed: {_SDK_IMPORT_ERROR}",
            failure_class=TransportFailureClass.PERMANENT.value,
        )
    if not callable(getattr(GateClient, "execute", None)) or not callable(getattr(GateClient, "activate", None)):
        # Fail closed and legibly rather than as an AttributeError deep in the
        # call: `execute` (the SDK owns TransportPacket construction) and
        # `activate` (Gate owns admission) are both required surfaces of the
        # supported Gate_SDK 1.2 release channel, not optional capabilities.
        raise GateIntegrationError(
            "constellation_node_sdk is too old: GateClient.execute() and GateClient.activate() "
            "are required. Bump the constellation-node-sdk pin in requirements.txt.",
            failure_class=TransportFailureClass.PERMANENT.value,
        )


# Admission receipts Gate issued, keyed by the exact identity Gate admitted. A
# process-global boolean would let a receipt for one Gate/key/tenant vouch for
# another; the key makes a change of GATE_URL, node, signing key id or tenant
# ask Gate again. Receipts are dropped when Gate later refuses an execute for
# the same identity, so a revoked grant is re-asked rather than assumed.
_ADMISSION_RECEIPTS: dict[tuple[Any, ...], Any] = {}
_ADMISSION_LOCK = threading.Lock()


def _admission_key(config: Any, tenant: str) -> tuple[Any, ...]:
    return (config.gate_url, config.local_node, config.signing_key_id, tenant, _ODOO_REQUIRED_ACTIONS)


def _forget_admission(config: Any, tenant: str) -> None:
    with _ADMISSION_LOCK:
        _ADMISSION_RECEIPTS.pop(_admission_key(config, tenant), None)


def ensure_admitted(client: Any, config: Any, tenant: str) -> Any:
    """Ask Gate whether this consumer is admitted for match + converge; fail closed otherwise.

    ``GateClient.activate`` and Gate's ``/v1/admission`` are supported surfaces
    of the released stack: neither is feature-detected, and no outcome is
    skipped. The SDK refuses up front when the configuration cannot prove an
    identity (``GateConfigurationError``: no signing key, a key without an id,
    no verifying key for Gate's receipt); Gate refuses a key it does not know
    (400) and withholds any action it has not granted
    (``GateAuthorizationError``, ``code == "action_not_permitted"``). Every
    refusal is a permanent, operator-visible configuration/authority failure.
    Never requests ``sync``. Never calls the registry.

    Returns Gate's ``ConsumerAccessReceipt`` for this identity.
    """
    key = _admission_key(config, tenant)
    with _ADMISSION_LOCK:
        receipt = _ADMISSION_RECEIPTS.get(key)
    if receipt is not None:
        return receipt
    try:
        receipt = _run_async(client.activate(required_actions=_ODOO_REQUIRED_ACTIONS, tenant=tenant))
    except Exception as exc:
        failure = failure_class_for(exc)
        if failure is None:
            raise
        detail = str(exc) or type(exc).__name__
        raise GateIntegrationError(detail, failure_class=failure.value) from exc
    with _ADMISSION_LOCK:
        _ADMISSION_RECEIPTS[key] = receipt
    return receipt


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
    # and reply_to from. Forced to odoo so it matches the Gate caller record.
    local_node = config.local_node
    tenant = resolve_tenant(env)
    ensure_admitted(client, config, tenant)
    user = env.user
    tenant_ctx = {
        "actor": tenant,
        "on_behalf_of": tenant,
        "originator": local_node,
        "org_id": tenant,
        "user_id": str(user.id) if user and user.id else None,
    }
    # Gate_SDK exposes the application-facing `GateClient.execute(action,
    # payload, ...)`, so Odoo never builds a TransportPacket. Every argument
    # below is a business input Odoo legitimately owns; the SDK owns the root
    # packet, source and reply-to identity (from GateClientConfig.local_node),
    # signing, HTTP, and response validation (pack ADR-007 — one SDK
    # invocation surface).
    #
    # Transport POLICY stays the SDK's:
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
                # `execute` writes this budget into the packet header AND
                # derives the network deadline from that same header, so the
                # advertised and actual budgets cannot diverge. Passing it
                # explicitly keeps the caller's validated config the single
                # source of the budget (pack ADR-009).
                timeout_ms=int(float(config.timeout_seconds) * 1000),
            )
        )
    except Exception as exc:
        failure = failure_class_for(exc)
        if failure is None:
            # Not a Gate transport outcome. A programming error reaching this
            # boundary is neither retryable nor permanent in the transport
            # sense; the caller's generic failure handling records it as
            # unknown/degraded rather than this bridge mislabelling it.
            raise
        if _SDK_AUTHORIZATION_ERRORS and isinstance(exc, _SDK_AUTHORIZATION_ERRORS):
            _forget_admission(config, tenant)
        # Timeout exceptions stringify to nothing: measured against a real Gate
        # transport, an exhausted caller budget surfaced with `str(exc) == ""`.
        # A timeout is the most likely real Gate failure and the caller budget
        # makes it an expected outcome, yet the operator saw "Gate enrichment
        # failed (retryable): " and the run stored validation_issues=[""] —
        # the classification was right and the reason was blank. Naming the
        # exception type keeps the durable record diagnosable; a blank
        # operator-visible reason is not a usable failure state (pack ADR-015).
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
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    action = get_matching_action(env)
    return send_action(
        env,
        action=action,
        payload=payload,
        correlation_id=correlation_id,
        compliance_tags=("ERP", "MATCHING"),
        idempotency_key=idempotency_key,
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
