"""ADR-014 invocation class — the Odoo adapter drives the REAL Gate_SDK.

Contract §13D: do not mock the SDK away. Patch only the external network seam,
then assert what the adapter handed to the SDK and, crucially, what it did NOT
touch. Every packet here is built by the installed ``GateClient`` and validated
by the installed SDK — Odoo contributes business inputs only.

Ownership proven here (GAR-ODOO-GATE-ALIGNMENT-001):

* the SDK parses ``GATE_URL`` + ``L9_*`` and Odoo supplies only its own
  overrides (node, caller budget, 30 s ceiling, Gate-only destination);
* ``GateClient.activate(required_actions=("match", "converge"))`` is asked
  before the first execute and Gate's answer is authoritative — a denied or
  unprovable identity is a permanent, visible failure, never a skip;
* the SDK's ``GateClientError.retryable`` verdict is the only source of
  Odoo's ``retryable`` / ``permanent`` category; anything that is not an SDK
  client error is not labelled a transport outcome at all.

Skipped when the SDK is absent (it is an Odoo.sh runtime dependency, and it
requires Python >= 3.12, so the pure-Python CI tier does not carry it). Run it
against a real install with a 3.12 interpreter to obtain the ADR-012
installed-package evidence.
"""

from __future__ import annotations

import json
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
    import httpx
    from constellation_node_sdk.gate import GateClient as _SdkGateClient
    from constellation_node_sdk.gate.admission import ADMISSION_ACTION, ADMISSION_PATH, ADMISSION_SCHEMA

    from plasticos_gate.services import gate_client as gc
    from plasticos_gate.services.gate_builders import build_operation_id
    from plasticos_gate.services.gate_config import GateIntegrationError

GATE_URL = "https://gate.example.internal"
RUN_ID = 7
TENANT = "plasticos"
ODOO_KEY_ID = "odoo-k1"
ODOO_KEY = "unit-test-odoo-key-material"
GATE_KEY_ID = "gate-k1"
GATE_KEY = "unit-test-gate-key-material"
_CLIENT_SRC = ROOT / "plasticos_gate" / "services" / "gate_client.py"
_CONFIG_SRC = ROOT / "plasticos_gate" / "services" / "gate_config.py"


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
        params = {"plasticos.gate.org_id": TENANT}
        params.update(overrides)
        self._icp = _Icp(params)
        self.cr = _Cursor()
        self.user = _User()

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return self._icp


class _FakeGate:
    """The network seam ONLY: an ``httpx.MockTransport`` standing in for Gate.

    The adapter still runs the real SDK ``GateClient``: config parsing,
    ``activate`` (which builds its own verifying client over the same injected
    transport), ``execute``, packet construction, budget resolution, routing
    policy, signing, outbound validation, response decoding and inbound
    signature verification all run unmodified. The packets under assertion are
    the exact wire artifacts the SDK produced from the adapter's business
    inputs; the replies are canonical packets signed with the Gate key.
    """

    def __init__(self) -> None:
        self.granted: tuple[str, ...] = ("converge", "match")
        self.admission_status = 200
        self.execute_status = 200
        self.sign_replies = True
        self.raise_on_execute: BaseException | None = None
        self.admission_requests: list = []
        self.execute_requests: list = []
        self.captured: dict = {}
        self.transport = httpx.MockTransport(self._handle)

    def _reply(self, request, wire, payload):
        from constellation_node_sdk import create_transport_packet, sign_transport_packet

        echo = create_transport_packet(
            action=wire.header.action,
            payload=payload,
            tenant={"actor": TENANT, "org_id": TENANT},
            source_node="gate",
            destination_node="odoo",
            reply_to="gate",
            correlation_id=wire.header.correlation_id,
        )
        if self.sign_replies:
            echo = sign_transport_packet(echo, key=GATE_KEY, key_id=GATE_KEY_ID, algorithm="hmac-sha256")
        return httpx.Response(200, json=echo.model_dump_json_dict(), request=request)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        from constellation_node_sdk import TransportPacket

        wire = TransportPacket.model_validate(json.loads(request.content))
        if request.url.path == ADMISSION_PATH:
            self.admission_requests.append(wire)
            self.captured["admission_packet"] = wire
            if self.admission_status != 200:
                return httpx.Response(
                    self.admission_status,
                    json={"detail": {"code": "invalid_transport_packet", "message": "unknown key"}},
                    request=request,
                )
            return self._reply(
                request,
                wire,
                {
                    "schema": ADMISSION_SCHEMA,
                    "gate_node": "gate",
                    "key_id": wire.security.signing_key_id,
                    "source_node": wire.address.source_node,
                    "scope": "restricted",
                    "scoped_actions": list(self.granted),
                    "granted_actions": list(self.granted),
                    "routable_actions": ["converge", "match", "sync"],
                },
            )
        self.execute_requests.append(wire)
        self.captured["packet"] = wire
        self.captured["url"] = str(request.url)
        self.captured["timeout_seconds"] = request.extensions["timeout"]["read"]
        if self.raise_on_execute is not None:
            raise self.raise_on_execute
        if self.execute_status == 403:
            return httpx.Response(
                403,
                json={"detail": {"code": "action_not_permitted", "message": "scope changed"}},
                request=request,
            )
        if self.execute_status != 200:
            return httpx.Response(self.execute_status, json={"detail": "no route"}, request=request)
        return self._reply(request, wire, {"state": "completed", "fields": {"website": "https://acme.example"}})


@pytest.fixture
def gate(monkeypatch):
    """A signed Odoo identity Gate admits for match + converge, over a fake Gate."""
    monkeypatch.setenv("GATE_URL", GATE_URL)
    monkeypatch.setenv("L9_NODE_NAME", "odoo")
    monkeypatch.setenv("L9_SIGNING_KEY", ODOO_KEY)
    monkeypatch.setenv("L9_SIGNING_KEY_ID", ODOO_KEY_ID)
    monkeypatch.setenv("L9_SIGNING_ALGORITHM", "hmac-sha256")
    monkeypatch.setenv("L9_VERIFYING_KEYS_JSON", json.dumps({GATE_KEY_ID: GATE_KEY}))
    monkeypatch.delenv("L9_REQUIRE_SIGNATURE", raising=False)
    fake = _FakeGate()

    class _SeamClient(_SdkGateClient):
        """The real SDK client, constructed over the fake Gate transport."""

        def __init__(self, config, *, transport=None):
            super().__init__(config, transport=fake.transport)
            fake.captured["config"] = config

    monkeypatch.setattr(gc, "GateClient", _SeamClient)
    gc._ADMISSION_RECEIPTS.clear()
    yield fake
    gc._ADMISSION_RECEIPTS.clear()


def _send(gate, env=None, **kwargs):
    payload = {"entity": {"id": f"res.partner:{RUN_ID}"}, "object_type": "plasticos"}
    result = gc.send_action(
        env or _Env(),
        action="converge",
        payload=payload,
        correlation_id=f"plasticos.enrichment.run:{RUN_ID}",
        compliance_tags=("ERP", "ENRICHMENT"),
        **kwargs,
    )
    return result, gate.captured["packet"]


# ── The adapter drives the real SDK ──────────────────────────────────────────


def test_adapter_produces_a_real_sdk_transport_packet(gate):
    """The object handed to the client is the SDK's own type, not an Odoo shape."""
    from constellation_node_sdk import TransportPacket

    _, packet = _send(gate)
    assert isinstance(packet, TransportPacket)


def test_sdk_validates_the_adapter_packet_as_gate_bound(gate):
    """Gate-only egress is proven by the SDK's validator accepting the packet (ADR-002)."""
    from constellation_node_sdk import validate_outbound_gate_packet

    _, packet = _send(gate)
    validate_outbound_gate_packet(packet, local_node="odoo", gate_node_name="gate")


def test_destination_is_gate_although_odoo_never_names_it(gate):
    """ADR-002/ADR-016 — routing is the SDK's default plus the SDK's validator."""
    _, packet = _send(gate)
    assert packet.address.destination_node == "gate"
    assert packet.address.source_node == "odoo"
    assert packet.address.reply_to == "odoo"
    assert "destination_node=" not in _CLIENT_SRC.read_text(encoding="utf-8")


def test_one_operation_identity_reaches_the_transport_header(gate):
    """ADR-006 — the header carries the same logical id the domain payload does."""
    odoo_ctx = {"model": "plasticos.enrichment.run", "record_id": RUN_ID, "db_name": "plasticos"}
    operation_id = build_operation_id(odoo_ctx)
    _, packet = _send(gate, idempotency_key=operation_id)
    assert packet.header.idempotency_key == operation_id
    assert packet.header.idempotency_key == "odoo:enrichment:plasticos:plasticos.enrichment.run:7"


def test_caller_budget_reaches_the_packet_and_the_client_config(gate):
    """ADR-009 — one validated budget governs both the header and the HTTP client."""
    _, packet = _send(gate)
    config = gate.captured["config"]
    assert config.timeout_seconds == 30.0
    assert packet.header.timeout_ms == 30_000
    assert packet.header.timeout_ms == int(config.timeout_seconds * 1000)
    # The network deadline the SDK actually used is derived from that same header.
    assert gate.captured["timeout_seconds"] == 30.0
    assert gate.captured["url"] == f"{GATE_URL}/v1/execute"


def test_domain_payload_rides_unchanged(gate):
    """Gate is transport, not a translator — the adapter must not rewrite the payload."""
    _, packet = _send(gate)
    assert packet.payload == {"entity": {"id": f"res.partner:{RUN_ID}"}, "object_type": "plasticos"}


def test_adapter_returns_the_canonical_response_payload(gate):
    """The adapter surfaces the canonical response without re-deriving transport truth."""
    result, _ = _send(gate)
    assert result["payload"]["state"] == "completed"
    assert result["failure_class"] is None
    assert result["packet"].header.action == "converge"


def test_transport_integrity_is_computed_by_the_sdk(gate):
    """ADR-001 — hashes exist on the packet, and Odoo computed none of them."""
    from constellation_node_sdk import compute_transport_hash

    _, packet = _send(gate)
    assert compute_transport_hash(packet) == packet.security.transport_hash
    src = _CLIENT_SRC.read_text(encoding="utf-8")
    for owned in ("compute_transport_hash", "compute_payload_hash", "sign_transport_packet"):
        assert owned not in src


def test_operator_retry_is_a_new_logical_operation():
    """Gate caches per identity — including an EIE domain failure — so a retry
    that reused the identity was answered from that cache forever."""
    odoo_ctx = {"model": "plasticos.enrichment.run", "record_id": RUN_ID, "db_name": "plasticos"}
    first = build_operation_id(odoo_ctx)
    second = build_operation_id(odoo_ctx, attempt=2)
    assert first == "odoo:enrichment:plasticos:plasticos.enrichment.run:7"
    assert second == "odoo:enrichment:plasticos:plasticos.enrichment.run:7:attempt-2"
    assert build_operation_id(odoo_ctx, attempt=1) == first


# ── V2: the SDK parses the canonical environment; Odoo overrides only its own ─


def test_config_is_the_sdk_env_builder_plus_odoo_owned_overrides_only(gate):
    """GATE-08/09/10 — signing posture is read by the SDK; Odoo pins node, budget, ceiling, destination."""
    _send(gate)
    config = gate.captured["config"]
    assert config.gate_url == GATE_URL
    assert config.local_node == "odoo"
    assert config.timeout_seconds == 30.0
    assert config.max_timeout_ms == 30_000
    assert config.allowed_gate_destination == "gate"
    # Read by the SDK from L9_*, never reconstructed by Odoo.
    assert config.signing_key_id == ODOO_KEY_ID
    assert config.signing_algorithm == "hmac-sha256"
    assert config.verifying_keys == {GATE_KEY_ID: GATE_KEY}
    assert config.require_signature is False  # L9_REQUIRE_SIGNATURE unset: the SDK's default, not Odoo's inference
    src = _CONFIG_SRC.read_text(encoding="utf-8")
    assert "get_gate_client_config_from_env(" in src
    for shadow in ("resolve_gate_signing", "_parse_verifying_keys", "_copy_supported_overrides", "model_copy("):
        assert shadow not in src, f"gate_config.py still carries SDK-owned configuration logic: {shadow}"
    assert "GateClientConfig(" not in src, "Odoo must not reconstruct GateClientConfig by hand"


def test_signed_packet_carries_the_environment_identity(gate):
    _, packet = _send(gate)
    assert packet.security.signing_key_id == ODOO_KEY_ID
    assert packet.security.signature_algorithm == "hmac-sha256"
    assert packet.security.signature
    # The material never appears in the packet.
    assert ODOO_KEY not in packet.model_dump_json()


def test_a_shorter_icp_budget_is_applied_and_the_ceiling_stays(gate):
    _, packet = _send(gate, env=_Env(**{"plasticos.gate.timeout_seconds": "5.5"}))
    config = gate.captured["config"]
    assert config.timeout_seconds == 5.5
    assert config.max_timeout_ms == 30_000
    assert packet.header.timeout_ms == 5_500
    assert gate.captured["timeout_seconds"] == 5.5


def test_a_budget_above_the_ceiling_is_rejected_before_any_network_call(gate):
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate, env=_Env(**{"plasticos.gate.timeout_seconds": "31"}))
    assert excinfo.value.failure_class == "permanent"
    assert not gate.admission_requests and not gate.execute_requests


def test_malformed_verifying_keys_fail_visibly_through_the_sdk(gate, monkeypatch):
    """GATE-09 — L9_VERIFYING_KEYS_JSON is validated by the SDK builder, not an Odoo parser."""
    monkeypatch.setenv("L9_VERIFYING_KEYS_JSON", "not-json")
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert "L9_VERIFYING_KEYS_JSON" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, ValueError)
    assert not gate.admission_requests


def test_key_id_without_material_fails_closed(gate, monkeypatch):
    from constellation_node_sdk.gate import GateConfigurationError

    monkeypatch.delenv("L9_SIGNING_KEY", raising=False)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert isinstance(excinfo.value.__cause__, GateConfigurationError)
    assert "L9_SIGNING_KEY" in str(excinfo.value)
    assert not gate.admission_requests and not gate.execute_requests


def test_material_without_key_id_fails_closed(gate, monkeypatch):
    from constellation_node_sdk.gate import GateConfigurationError

    monkeypatch.delenv("L9_SIGNING_KEY_ID", raising=False)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert isinstance(excinfo.value.__cause__, GateConfigurationError)
    assert ODOO_KEY not in str(excinfo.value)
    assert not gate.admission_requests


def test_unsigned_identity_cannot_be_admitted(gate, monkeypatch):
    """An unsigned consumer has no identity Gate can verify: a configuration failure, never a silent send."""
    from constellation_node_sdk.gate import GateConfigurationError

    monkeypatch.delenv("L9_SIGNING_KEY", raising=False)
    monkeypatch.delenv("L9_SIGNING_KEY_ID", raising=False)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert isinstance(excinfo.value.__cause__, GateConfigurationError)
    assert not gate.execute_requests


def test_require_signature_without_verifying_keys_fails_closed(gate, monkeypatch):
    monkeypatch.setenv("L9_REQUIRE_SIGNATURE", "1")
    monkeypatch.delenv("L9_VERIFYING_KEYS_JSON", raising=False)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert not gate.execute_requests


def test_require_signature_makes_the_sdk_verify_gate_replies(gate, monkeypatch):
    from constellation_node_sdk.gate import GateSecurityError

    monkeypatch.setenv("L9_REQUIRE_SIGNATURE", "1")
    _send(gate)
    assert gate.captured["config"].require_signature is True
    assert gate.captured["config"].verify_response_signatures is True
    gc._ADMISSION_RECEIPTS.clear()
    gate.sign_replies = False
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert isinstance(excinfo.value.__cause__, GateSecurityError)


# ── V3: admission is authoritative, keyed, and asks for match + converge only ─


def test_send_asks_gate_for_admission_before_executing(gate):
    _send(gate)
    probe = gate.captured["admission_packet"]
    assert probe.header.action == ADMISSION_ACTION
    assert probe.address.destination_node == "gate"
    assert probe.security.signing_key_id == ODOO_KEY_ID
    assert len(gate.admission_requests) == 1 and len(gate.execute_requests) == 1
    (receipt,) = gc._ADMISSION_RECEIPTS.values()
    assert receipt.admitted
    assert receipt.required_actions == ("match", "converge")
    assert "sync" not in receipt.required_actions
    assert receipt.key_id == ODOO_KEY_ID


def test_admission_is_keyed_by_identity_not_a_process_global_boolean(gate):
    _send(gate)
    _send(gate)
    assert len(gate.admission_requests) == 1, "the same admitted identity is not re-asked"
    (key,) = gc._ADMISSION_RECEIPTS
    assert key == (GATE_URL, "odoo", ODOO_KEY_ID, TENANT, ("match", "converge"))
    # A different tenant is a different identity: Gate is asked again.
    _send(gate, env=_Env(**{"plasticos.gate.org_id": "other-tenant"}))
    assert len(gate.admission_requests) == 2
    assert len(gc._ADMISSION_RECEIPTS) == 2
    assert not hasattr(gc, "_activated_ok")
    assert not hasattr(gc, "_maybe_activate")


def test_denied_admission_is_permanent_and_nothing_executes(gate):
    """GATE-11 — Gate did not grant `match`: typed authorization failure, non-retryable."""
    from constellation_node_sdk.gate import GateAuthorizationError

    gate.granted = ("converge",)
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    cause = excinfo.value.__cause__
    assert isinstance(cause, GateAuthorizationError)
    assert cause.code == "action_not_permitted"
    assert cause.retryable is False
    assert excinfo.value.failure_class == "permanent"
    assert "match" in str(excinfo.value)
    assert not gate.execute_requests
    assert not gc._ADMISSION_RECEIPTS


def test_unknown_key_is_rejected_as_permanent(gate):
    """Gate answers an unknown key with 400, not 403: still non-retryable, still no execute."""
    from constellation_node_sdk.gate import GateAuthorizationError, GateHTTPError

    gate.admission_status = 400
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    cause = excinfo.value.__cause__
    assert isinstance(cause, GateHTTPError) and not isinstance(cause, GateAuthorizationError)
    assert cause.status_code == 400
    assert excinfo.value.failure_class == "permanent"
    assert not gate.execute_requests


def test_a_gate_without_the_admission_endpoint_is_not_skipped(gate):
    """GATE-12 — /v1/admission is part of the released stack; a 404 is a permanent failure, not compatibility."""
    gate.admission_status = 404
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert not gate.execute_requests
    assert "skipping" not in _CLIENT_SRC.read_text(encoding="utf-8")


def test_an_authority_refusal_on_execute_drops_the_cached_receipt(gate):
    from constellation_node_sdk.gate import GateAuthorizationError

    _send(gate)
    assert len(gc._ADMISSION_RECEIPTS) == 1
    gate.execute_status = 403
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert isinstance(excinfo.value.__cause__, GateAuthorizationError)
    assert excinfo.value.failure_class == "permanent"
    assert not gc._ADMISSION_RECEIPTS, "a revoked grant is re-asked, not assumed"


# ── V4: retryability is the SDK's verdict, projected — never re-derived ──────


def _sdk_failures():
    from constellation_node_sdk.gate import (
        GateAuthorizationError,
        GateConfigurationError,
        GateConnectionError,
        GatePolicyError,
        GateResponseError,
        GateSecurityError,
        GateTimeoutError,
    )

    return [
        (GateConnectionError("refused"), "retryable"),
        (GateTimeoutError("", timeout_seconds=30.0), "retryable"),
        (GateAuthorizationError("denied", status_code=403, response_text="{}"), "permanent"),
        (GateConfigurationError("bad config"), "permanent"),
        (GateSecurityError("bad signature", direction="inbound"), "permanent"),
        (GateResponseError("not a packet", body={}), "permanent"),
        (GatePolicyError("not gate-bound"), "permanent"),
    ]


def test_sdk_typed_errors_project_onto_odoo_categories_by_their_own_verdict():
    for exc, expected in _sdk_failures():
        assert exc.retryable is (expected == "retryable"), type(exc).__name__
        assert gc.failure_class_for(exc).value == expected, type(exc).__name__


@pytest.mark.parametrize("status", [503, 502, 429, 408, 400, 404, 422, 501])
def test_http_status_retryability_is_the_sdks_not_odoos(status):
    """Odoo holds no status table: the projection follows `GateHTTPError.retryable` whatever it says."""
    from constellation_node_sdk.gate import GateHTTPError

    exc = GateHTTPError("gate answered", status_code=status, response_text="{}")
    assert gc.failure_class_for(exc).value == ("retryable" if exc.retryable else "permanent")
    src = _CLIENT_SRC.read_text(encoding="utf-8")
    for table in ("408", "429", "501", "505", "status_code", "status in"):
        assert table not in src, f"gate_client.py re-derives HTTP transport policy: {table!r}"


def test_non_sdk_exceptions_are_not_transport_outcomes():
    assert gc.failure_class_for(RuntimeError("boom")) is None
    assert gc.failure_class_for(TimeoutError()) is None
    assert gc.failure_class_for(ConnectionError()) is None
    assert gc.failure_class_for(ValueError("destination must be gate")) is None


def test_a_programming_error_at_the_boundary_is_not_labelled_a_gate_failure(gate):
    gate.raise_on_execute = RuntimeError("socket closed mid-handshake")
    with pytest.raises(RuntimeError):
        _send(gate)


def test_send_failure_is_classified_without_reading_the_message(gate):
    """ADR-015 — a transport failure fails closed with a diagnosable reason."""
    from constellation_node_sdk.gate import GateTimeoutError

    gate.raise_on_execute = httpx.ConnectTimeout("")  # stringifies to empty, as in production
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert isinstance(excinfo.value.__cause__, GateTimeoutError)
    assert excinfo.value.__cause__.retryable is True
    assert excinfo.value.failure_class == "retryable"
    assert str(excinfo.value)  # never a blank operator-visible reason
    assert "ConnectTimeout" in str(excinfo.value)


def test_gate_404_reaches_the_operator_as_permanent(gate):
    """An unknown action is a 404 from Gate — a configuration fault, not a retry."""
    from constellation_node_sdk.gate import GateHTTPError

    gate.execute_status = 404
    with pytest.raises(GateIntegrationError) as excinfo:
        _send(gate)
    assert excinfo.value.failure_class == "permanent"
    assert isinstance(excinfo.value.__cause__, GateHTTPError)
    assert excinfo.value.__cause__.status_code == 404
    assert excinfo.value.__cause__.retryable is False


def test_the_bridge_imports_no_httpx_and_no_sdk_exception_taxonomy():
    """GAP-01/GAP-02 — the SDK promises callers never need httpx to classify a Gate failure."""
    src = _CLIENT_SRC.read_text(encoding="utf-8")
    assert "import httpx" not in src
    assert "httpx." not in src
    assert "classify_transport_failure" not in src
    for grouped in (
        "GateConnectionError",
        "GateTimeoutError",
        "GateHTTPError",
        "GateSecurityError",
        "GateResponseError",
    ):
        assert f"import {grouped}" not in src and f"    {grouped}," not in src, (
            f"gate_client.py imports {grouped} — grouping SDK exception subclasses re-derives retryability"
        )
