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
    from constellation_node_sdk.gate import GateClient as _SdkGateClient

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
            "plasticos.gate.signing_key_id": "",
            "plasticos.gate.verify_response_signatures": "0",
        }
        params.update(overrides)
        self._icp = _Icp(params)
        self.cr = _Cursor()
        self.user = _User()

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return self._icp


class _CapturingClient(_SdkGateClient if _SDK_AVAILABLE else object):
    """Stands in for the network seam ONLY.

    It IS the real SDK ``GateClient``: ``execute`` and ``send_to_gate`` —
    packet construction, budget resolution, routing policy, signing, outbound
    validation, response decoding and inbound validation — run unmodified.
    Only ``_post_json`` (the single HTTP request) is replaced, so the packet
    under assertion is the exact wire artifact the real SDK produced from the
    adapter's business inputs.
    """

    captured: dict = {}

    def __init__(self, config):
        super().__init__(config)
        type(self).captured["config"] = config

    async def _post_json(self, *, url, json_body, timeout_seconds, headers=None, params=None):
        import httpx
        from constellation_node_sdk import TransportPacket, create_transport_packet

        wire_packet = TransportPacket.model_validate(json_body)
        type(self).captured["packet"] = wire_packet
        type(self).captured["url"] = url
        type(self).captured["timeout_seconds"] = timeout_seconds
        # Echo a canonical response packet built by the SDK itself.
        echo = create_transport_packet(
            action=wire_packet.header.action,
            payload={"state": "completed", "fields": {"website": "https://acme.example"}},
            tenant={"actor": "plasticos", "org_id": "plasticos"},
            source_node="gate",
            destination_node="odoo",
            reply_to="gate",
            correlation_id=wire_packet.header.correlation_id,
        )
        return httpx.Response(200, json=echo.model_dump_json_dict(), request=httpx.Request("POST", url))


@pytest.fixture
def captured(monkeypatch):
    _CapturingClient.captured = {}
    monkeypatch.setattr(gc, "GateClient", _CapturingClient)
    return _CapturingClient.captured


def _send(captured, env=None, **kwargs):
    payload = {"entity": {"id": f"res.partner:{RUN_ID}"}, "object_type": "plasticos"}
    result = gc.send_action(
        env or _Env(),
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
    # The network deadline the SDK actually used is derived from that same header.
    assert captured["timeout_seconds"] == 30.0
    assert captured["url"] == f"{GATE_URL}/v1/execute"


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
        async def _post_json(self, **kwargs):
            raise httpx.ConnectTimeout("")  # stringifies to empty, as in production

    monkeypatch.setattr(gc, "GateClient", _Failing)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(captured)
    assert excinfo.value.failure_class == "retryable"
    assert str(excinfo.value)  # never a blank operator-visible reason
    assert "ConnectTimeout" in str(excinfo.value)


# ── Operation identity across operator retries (ADR-006) ─────────────────────


def test_operator_retry_is_a_new_logical_operation():
    """Gate caches per identity — including an EIE domain failure — so a retry
    that reused the identity was answered from that cache forever."""
    odoo_ctx = {"model": "plasticos.enrichment.run", "record_id": RUN_ID, "db_name": "plasticos"}
    first = build_operation_id(odoo_ctx)
    second = build_operation_id(odoo_ctx, attempt=2)
    assert first == "odoo:enrichment:plasticos:plasticos.enrichment.run:7"
    assert second == "odoo:enrichment:plasticos:plasticos.enrichment.run:7:attempt-2"
    assert build_operation_id(odoo_ctx, attempt=1) == first


# ── Failure classification is keyed to the SDK's typed errors ────────────────


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (503, "retryable"),
        (502, "retryable"),
        (429, "retryable"),
        (408, "retryable"),
        (400, "permanent"),
        (404, "permanent"),
        (422, "permanent"),
        (501, "permanent"),
    ],
)
def test_sdk_http_error_is_classified_by_status(status, expected):
    from constellation_node_sdk.gate import GateHTTPError

    exc = GateHTTPError("gate answered", status_code=status, response_text="{}")
    assert gc.classify_transport_failure(exc).value == expected


def test_sdk_typed_errors_carry_their_retryability():
    from constellation_node_sdk.gate import (
        GateConfigurationError,
        GateConnectionError,
        GatePolicyError,
        GateResponseError,
        GateSecurityError,
        GateTimeoutError,
    )

    classify = gc.classify_transport_failure
    assert classify(GateTimeoutError("", timeout_seconds=30.0)).value == "retryable"
    assert classify(GateConnectionError("refused")).value == "retryable"
    assert classify(GateSecurityError("bad signature", direction="inbound")).value == "permanent"
    assert classify(GateResponseError("not a packet", body={})).value == "permanent"
    assert classify(GateConfigurationError("bad config")).value == "permanent"
    assert classify(GatePolicyError("not gate-bound")).value == "permanent"


def test_gate_404_reaches_the_operator_as_permanent(captured, monkeypatch):
    """An unknown action is a 404 from Gate — a configuration fault, not a retry."""
    import httpx
    from constellation_node_sdk.gate import GateHTTPError

    from plasticos_gate.services.gate_config import GateIntegrationError

    class _NotFound(_CapturingClient):
        async def _post_json(self, *, url, **kwargs):
            return httpx.Response(404, json={"detail": "no route"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(gc, "GateClient", _NotFound)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(captured)
    assert excinfo.value.failure_class == "permanent"
    assert isinstance(excinfo.value.__cause__, GateHTTPError)
    assert excinfo.value.__cause__.status_code == 404


# ── Packet signing: key material from the environment only ───────────────────


def test_unsigned_by_default(captured):
    _, packet = _send(captured)
    config = captured["config"]
    assert config.signing_key is None
    assert config.require_signature is False
    assert packet.security.signature is None


def test_signing_key_from_environment_signs_the_packet(captured, monkeypatch):
    monkeypatch.setenv("PLASTICOS_GATE_SIGNING_KEY", "unit-test-key-material")
    env = _Env(**{"plasticos.gate.signing_key_id": "odoo-k1"})
    _, packet = _send(captured, env=env)
    config = captured["config"]
    assert config.signing_key_id == "odoo-k1"
    assert config.signing_algorithm == "hmac-sha256"
    assert config.require_signature is True
    assert packet.security.signing_key_id == "odoo-k1"
    assert packet.security.signature_algorithm == "hmac-sha256"
    assert packet.security.signature
    # The material never appears in the packet or in the ICP surface.
    assert "unit-test-key-material" not in packet.model_dump_json()


def test_key_id_without_material_fails_closed(captured, monkeypatch):
    from plasticos_gate.services.gate_config import GateIntegrationError

    monkeypatch.delenv("PLASTICOS_GATE_SIGNING_KEY", raising=False)
    env = _Env(**{"plasticos.gate.signing_key_id": "odoo-k1"})
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(captured, env=env)
    assert excinfo.value.failure_class == "permanent"
    assert "PLASTICOS_GATE_SIGNING_KEY" in str(excinfo.value)


def test_material_without_key_id_fails_closed(captured, monkeypatch):
    from plasticos_gate.services.gate_config import GateIntegrationError

    monkeypatch.setenv("PLASTICOS_GATE_SIGNING_KEY", "unit-test-key-material")
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(captured, env=_Env())
    assert excinfo.value.failure_class == "permanent"
    assert "unit-test-key-material" not in str(excinfo.value)


def test_response_verification_without_keys_fails_closed(captured, monkeypatch):
    from plasticos_gate.services.gate_config import GateIntegrationError

    monkeypatch.delenv("PLASTICOS_GATE_SIGNING_KEY", raising=False)
    monkeypatch.delenv("PLASTICOS_GATE_VERIFYING_KEYS_JSON", raising=False)
    env = _Env(**{"plasticos.gate.verify_response_signatures": "1"})
    with pytest.raises(GateIntegrationError):
        _send(captured, env=env)


def test_verifying_keys_json_is_validated(captured, monkeypatch):
    from plasticos_gate.services.gate_config import GateIntegrationError

    monkeypatch.setenv("PLASTICOS_GATE_VERIFYING_KEYS_JSON", "not-json")
    with pytest.raises(GateIntegrationError):
        _send(captured, env=_Env())
    monkeypatch.setenv("PLASTICOS_GATE_VERIFYING_KEYS_JSON", '{"gate-k1": "gate-material"}')
    _, _packet = _send(captured, env=_Env())
    assert captured["config"].verifying_keys == {"gate-k1": "gate-material"}
