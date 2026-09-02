"""ADR-014 invocation class — the Odoo adapter drives the REAL Gate_SDK.

Contract §13D: do not mock the SDK away. Patch only the external network seam,
then assert what the adapter handed to the SDK and, crucially, what it did NOT
touch. Every packet here is built by the installed ``create_transport_packet``
and validated by the installed SDK — Odoo contributes business inputs only.

Skipped when the SDK is absent (it is an Odoo.sh runtime dependency, and it
requires Python >= 3.12, so the pure-Python CI tier does not carry it). Run it
against a real install with a 3.12 interpreter to obtain the ADR-012
installed-package evidence.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# NOTE: `tests/__init__.py` eagerly imports every test module, so a module-level
# `pytest.importorskip` would raise Skipped during that package import and abort
# collection of the WHOLE suite on an interpreter without the SDK. Use a soft
# import plus a skip mark instead: absent SDK skips this module only.
try:  # pragma: no cover - environment-dependent
    import constellation_node_sdk  # noqa: F401

    _SDK_AVAILABLE = True
except Exception:  # pragma: no cover
    _SDK_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SDK_AVAILABLE,
    reason="Gate SDK is an Odoo.sh runtime dependency (requires Python >= 3.12)",
)

if _SDK_AVAILABLE:
    from plasticos_gate.services import gate_client as gc
    from plasticos_gate.services.gate_builders import build_operation_id

GATE_URL = "https://gate.example.internal"
RUN_ID = 7


class _Icp:
    def __init__(self, params: dict[str, str]) -> None:
        self._params = params

    def sudo(self):
        return self

    def get_param(self, key, default=None):
        return self._params.get(key, default)


class _Cursor:
    dbname = "plasticos"


class _User:
    id = 2


class _Env:
    """Minimal Odoo env: only what the adapter actually reads."""

    def __init__(self, **overrides: str) -> None:
        params = {
            "plasticos.gate.url": GATE_URL,
            "plasticos.gate.local_node": "odoo",
            "plasticos.gate.org_id": "plasticos",
        }
        params.update(overrides)
        self._icp = _Icp(params)
        self.cr = _Cursor()
        self.user = _User()

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return self._icp


class _CapturingClient:
    """Stands in for the network seam ONLY.

    It is constructed with the real ``GateClientConfig`` the adapter built, and
    it receives the real ``TransportPacket`` the real SDK factory produced. The
    packet under assertion is genuine; only the socket is not.
    """

    captured: dict = {}

    def __init__(self, config):
        type(self).captured["config"] = config

    async def send_to_gate(self, packet):
        type(self).captured["packet"] = packet
        # Echo a canonical response packet built by the SDK itself.
        from constellation_node_sdk import create_transport_packet

        return create_transport_packet(
            action=packet.header.action,
            payload={"state": "completed", "fields": {"website": "https://acme.example"}},
            tenant={"actor": "plasticos", "org_id": "plasticos"},
            source_node="gate",
            destination_node="odoo",
            reply_to="gate",
            correlation_id=packet.header.correlation_id,
        )


@pytest.fixture
def captured(monkeypatch):
    _CapturingClient.captured = {}
    monkeypatch.setattr(gc, "GateClient", _CapturingClient)
    return _CapturingClient.captured


def _send(captured, **kwargs):
    payload = {"entity": {"id": f"res.partner:{RUN_ID}"}, "object_type": "plasticos"}
    result = gc.send_action(
        _Env(),
        action="converge",
        payload=payload,
        correlation_id=f"plasticos.enrichment.run:{RUN_ID}",
        compliance_tags=("ERP", "ENRICHMENT"),
        **kwargs,
    )
    return result, captured["packet"]


def test_adapter_produces_a_real_sdk_transport_packet(captured):
    """The object handed to the client is the SDK's own type, not an Odoo shape."""
    from constellation_node_sdk import TransportPacket

    _, packet = _send(captured)
    assert isinstance(packet, TransportPacket)


def test_sdk_validates_the_adapter_packet_as_gate_bound(captured):
    """The packet the adapter built passes the SDK's own outbound Gate policy.

    This is the assertion that matters for ADR-002: Gate-only egress is proven
    by the SDK's validator accepting the packet, not by Odoo asserting its own
    string.
    """
    from constellation_node_sdk import validate_outbound_gate_packet

    _, packet = _send(captured)
    validate_outbound_gate_packet(packet, local_node="odoo", gate_node_name="gate")


def test_destination_is_gate_although_odoo_never_names_it(captured):
    """ADR-002/ADR-016 — routing is the SDK's default plus the SDK's validator."""
    _, packet = _send(captured)
    assert packet.address.destination_node == "gate"
    assert packet.address.source_node == "odoo"
    assert packet.address.reply_to == "odoo"
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "destination_node=" not in src


def test_one_operation_identity_reaches_the_transport_header(captured):
    """ADR-006 — the header carries the same logical id the domain payload does."""
    odoo_ctx = {"model": "plasticos.enrichment.run", "record_id": RUN_ID, "db_name": "plasticos"}
    operation_id = build_operation_id(odoo_ctx)
    _, packet = _send(captured, idempotency_key=operation_id)
    assert packet.header.idempotency_key == operation_id
    assert packet.header.idempotency_key == "odoo:enrichment:plasticos:plasticos.enrichment.run:7"


def test_caller_budget_reaches_the_packet_and_the_client_config(captured):
    """ADR-009 — one validated budget governs both the header and the HTTP client."""
    _, packet = _send(captured)
    config = captured["config"]
    assert config.timeout_seconds == 30.0
    assert packet.header.timeout_ms == 30_000
    assert packet.header.timeout_ms == int(config.timeout_seconds * 1000)


def test_domain_payload_rides_unchanged(captured):
    """Gate is transport, not a translator — the adapter must not rewrite the payload."""
    _, packet = _send(captured)
    assert packet.payload == {"entity": {"id": f"res.partner:{RUN_ID}"}, "object_type": "plasticos"}


def test_adapter_returns_the_canonical_response_payload(captured):
    """The adapter surfaces the canonical response without re-deriving transport truth."""
    result, _ = _send(captured)
    assert result["payload"]["state"] == "completed"
    assert result["failure_class"] is None
    assert result["packet"].header.action == "converge"


def test_transport_integrity_is_computed_by_the_sdk(captured):
    """ADR-001 — hashes exist on the packet, and Odoo computed none of them."""
    from constellation_node_sdk import compute_transport_hash

    _, packet = _send(captured)
    assert compute_transport_hash(packet) == packet.security.transport_hash
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    for owned in ("compute_transport_hash", "compute_payload_hash", "sign_transport_packet"):
        assert owned not in src


def test_send_failure_is_classified_without_reading_the_message(captured, monkeypatch):
    """ADR-015 — a transport failure fails closed with a diagnosable reason."""
    import httpx

    from plasticos_gate.services.gate_config import GateIntegrationError

    class _Failing(_CapturingClient):
        async def send_to_gate(self, packet):
            raise httpx.ConnectTimeout("")  # stringifies to empty, as in production

    monkeypatch.setattr(gc, "GateClient", _Failing)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(captured)
    assert excinfo.value.failure_class == "retryable"
    assert str(excinfo.value)  # never a blank operator-visible reason
    assert "ConnectTimeout" in str(excinfo.value)
