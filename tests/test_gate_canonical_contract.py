"""Canonical Gate contract: Odoo emits EnrichRequest, consumes EnrichResponse.

The rail this pins:

    Odoo build_converge_request
      -> Gate_SDK GateClient.execute(action="converge", payload=...)
         (the SDK builds the TransportPacket; Odoo never does)
      -> Constellation.Gate
      -> EIE canonical EnrichRequest handler
      -> EnrichResponse
      -> Odoo map_converge_response

Odoo is a domain producer/consumer on that rail. It owns neither transport nor
routing, and it must not grow a second converge dialect beside the canonical
one. The negative tests below are architecture regression guards: each names a
specific way the contract previously drifted, or could drift back.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import (  # noqa: E402
    IDEMPOTENCY_DIGEST_HEX_CHARS,
    build_converge_request,
    build_idempotency_key,
    build_odoo_context,
)
from plasticos_gate.services.gate_config import (  # noqa: E402
    DEFAULT_GATE_TIMEOUT_SECONDS,
    MAX_GATE_TIMEOUT_SECONDS,
    GateIntegrationError,
    resolve_gate_timeout_seconds,
)
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    map_converge_response,
    partner_writeback_from_converge,
)

PARTNER_ID = 55
RUN_ID = 7
ENTITY_REF = f"res.partner:{PARTNER_ID}"


class _FakePartner:
    _fields: dict = {}

    def __init__(self, partner_id: int):
        self.id = partner_id


class _FakeRun:
    _name = "plasticos.enrichment.run"
    source_ids = ()

    def __init__(self, run_id: int, partner: _FakePartner):
        self.id = run_id
        self.partner_id = partner


class _FakeEnv:
    def __init__(self, db_name: str = "plasticos"):
        self.company = type("C", (), {"id": 1})()
        self.user = type("U", (), {"id": 2})()
        self.cr = type("R", (), {"dbname": db_name})()


def _request():
    return build_converge_request(_FakeEnv(), _FakeRun(RUN_ID, _FakePartner(PARTNER_ID)))


def _payload():
    return _request().to_dict()


# ── PATCH 8 — the exact request the live builder emits ─────────────────────
#
# Source: plasticos_gate/services/gate_builders.py::build_converge_request
#         -> plasticos_gate/services/gate_contracts.py::ConvergeRequest.to_dict
# Semantically identical to the fixture in the EIE repo at
# tests/unit/test_odoo_cross_repo_contract.py::_odoo_builder_payload — kept in
# sync by shape, never by a runtime dependency between the two repositories.


def test_payload_is_enrich_request_shaped():
    payload = _payload()
    assert set(payload) >= {"entity", "object_type", "objective", "max_variations"}
    assert isinstance(payload["entity"], dict)
    assert isinstance(payload["max_variations"], int)


def test_canonical_identity_is_on_the_entity():
    entity = _payload()["entity"]
    assert entity["id"] == ENTITY_REF


def test_compatibility_alias_carries_the_same_value():
    entity = _payload()["entity"]
    assert entity["_odoo_entity_id"] == entity["id"]


def test_odoo_context_travels_as_metadata():
    odoo = _payload()["odoo"]
    assert odoo["model"] == "plasticos.enrichment.run"
    assert odoo["record_id"] == RUN_ID
    assert odoo["correlation_id"] == f"plasticos.enrichment.run:{RUN_ID}"


def test_kb_context_declares_the_domain_explicitly():
    """EIE resolves the KB domain `domain_id` -> `domain` -> `kb_context` ->
    `object_type`. Relying on object_type is the last fallback and works only
    because Odoo happens to carry the domain there; kb_context states it."""
    payload = _payload()
    assert payload["kb_context"] == "plasticos"
    assert payload["kb_context"] == payload["object_type"]


def test_payload_validates_as_a_canonical_enrich_request():
    """EIE's canonical branch does `EnrichRequest.model_validate(payload)`, so
    the payload must carry only EnrichRequest-legal keys plus the odoo context."""
    enrich_request_fields = {
        "entity",
        "object_type",
        "objective",
        "max_variations",
        "kb_context",
        "idempotency_key",
        "schema",
    }
    extra = set(_payload()) - enrich_request_fields - {"odoo"}
    assert not extra, f"payload carries non-EnrichRequest keys: {sorted(extra)}"


def test_mapper_keeps_fields_eie_no_longer_truncates():
    """The canonical branch returns EnrichResponse untruncated — the old adapter
    clipped `fields` to the eight partner keys. Odoo keeps the full set for
    audit and enforces its allowlist only at the writeback boundary."""
    resp = map_converge_response(_eie_response(fields={"website": "https://a.example", "polymer_type": "HDPE"}))
    assert resp.final_fields == {"website": "https://a.example", "polymer_type": "HDPE"}
    assert partner_writeback_from_converge(resp) == {"website": "https://a.example"}


# ── PATCH 11 — negative: no drift into the alternate adapter dialect ───────


def test_request_does_not_emit_entity_snapshot():
    """`entity_snapshot` belongs to EIE's alternate adapter dialect, not here."""
    assert "entity_snapshot" not in _payload()


def test_request_does_not_emit_a_top_level_entity_id():
    """A top-level entity_id would fork the canonical EnrichRequest contract."""
    assert "entity_id" not in _payload()


def test_request_does_not_emit_response_side_keys():
    payload = _payload()
    for forbidden in ("status", "final_fields", "writeback"):
        assert forbidden not in payload


def test_gate_client_holds_no_eie_peer_address():
    """O2 — Odoo addresses Gate, never EIE. Routing is Gate's job."""
    for name in ("gate_client.py", "gate_config.py", "gate_builders.py"):
        lowered = (ROOT / "plasticos_gate" / "services" / name).read_text(encoding="utf-8").lower()
        for probe in ("enrichment.inference", "eie_url", "eie_endpoint", "/v1/execute", "eie.", ":8000"):
            assert probe not in lowered, f"{name} addresses a peer directly: {probe}"


def test_destination_node_is_gate():
    """Gate is the only destination — now enforced by NOT naming one at all.

    Before the SDK owned packet construction, Odoo passed
    ``destination_node="gate"`` explicitly and this asserted that literal. The
    invariant is stronger post-migration: the bridge names no destination
    whatsoever (it cannot address a peer even by mistake), and the config pins
    the only destination the SDK will accept.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "destination_node" not in src, "the bridge must not name a destination; Gate routing is the SDK's"
    config_src = (ROOT / "plasticos_gate" / "services" / "gate_config.py").read_text(encoding="utf-8")
    assert 'allowed_gate_destination="gate"' in config_src


# ── PATCH 9 — canonical EnrichResponse consumption ────────────────────────


def _eie_response(**overrides):
    base = {
        "state": "completed",
        "fields": {"website": "https://acme.example", "phone": "555-0100"},
        "pass_count": 2,
        "tokens_used": 1200,
        "confidence": 0.9,
    }
    base.update(overrides)
    return base


def test_mapper_accepts_canonical_state_fields_response():
    resp = map_converge_response(_eie_response())
    assert resp.state == "completed"
    assert resp.status == "ok"  # derived from state, not read off the wire
    assert resp.final_fields == {"website": "https://acme.example", "phone": "555-0100"}


def test_mapper_does_not_require_status_final_fields_or_writeback():
    """A response carrying none of the obsolete envelope still maps cleanly."""
    payload = _eie_response()
    for absent in ("status", "final_fields", "writeback"):
        assert absent not in payload
    assert map_converge_response(payload).status == "ok"


def test_mapper_fails_closed_without_an_explicit_completed_state():
    for payload in ({}, {"state": ""}, {"fields": {"website": "x"}}):
        assert map_converge_response(payload).status != "ok"


def test_mapper_reports_failure_reason_over_state():
    resp = map_converge_response(_eie_response(state="failed", failure_reason="provider timeout"))
    assert resp.status == "provider timeout"


# ── PATCH 7 — writeback safety survives the contract repair ────────────────


def test_writeback_proposal_is_allowlisted():
    resp = map_converge_response(_eie_response(fields={"website": "https://a.example", "vat": "SECRET", "id": 9}))
    proposal = partner_writeback_from_converge(resp)
    assert proposal == {"website": "https://a.example"}


def test_writeback_proposal_drops_empty_values():
    resp = map_converge_response(_eie_response(fields={"website": "", "phone": None, "city": "NC"}))
    assert partner_writeback_from_converge(resp) == {"city": "NC"}


# ── PATCH 4 — deterministic transport idempotency key ─────────────────────


def _ctx(record_id: int = RUN_ID, db_name: str = "plasticos"):
    return build_odoo_context(_FakeEnv(db_name), model="plasticos.enrichment.run", record_id=record_id).to_dict()


def test_idempotency_key_is_stable_for_a_true_replay():
    payload = _payload()
    assert build_idempotency_key(payload, _ctx()) == build_idempotency_key(payload, _ctx())


def test_idempotency_key_differs_across_runs():
    payload = _payload()
    assert build_idempotency_key(payload, _ctx(7)) != build_idempotency_key(payload, _ctx(8))


def test_idempotency_key_differs_when_the_payload_changed():
    """An operator retry after the partner was edited is a different request."""
    a = _payload()
    b = _payload()
    b["entity"]["name"] = "Acme Recycling Ltd"
    assert build_idempotency_key(a, _ctx()) != build_idempotency_key(b, _ctx())


def test_idempotency_key_is_database_scoped():
    payload = _payload()
    assert build_idempotency_key(payload, _ctx(db_name="prod")) != build_idempotency_key(
        payload, _ctx(db_name="staging")
    )


def test_idempotency_key_carries_no_timestamp_or_randomness():
    payload = _payload()
    keys = {build_idempotency_key(payload, _ctx()) for _ in range(5)}
    assert len(keys) == 1


def test_idempotency_key_is_none_without_run_identity():
    assert build_idempotency_key(_payload(), {}) is None


def test_idempotency_key_is_not_in_the_business_payload():
    """It is a transport header. The payload stays a plain EnrichRequest."""
    assert "idempotency_key" not in _payload()


def test_idempotency_digest_is_128_bits_of_lowercase_hex():
    """32 hex chars = 128 bits. Narrower is a needless birthday risk on a replay key."""
    digest = build_idempotency_key(_payload(), _ctx()).rsplit(":", 1)[1]
    assert len(digest) == IDEMPOTENCY_DIGEST_HEX_CHARS == 32
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_idempotency_digest_is_a_sha256_prefix():
    """Pins the algorithm, so a future edit cannot quietly swap in a weaker hash."""
    payload = _payload()
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    assert build_idempotency_key(payload, _ctx()).endswith(expected[:32])


def test_idempotency_key_keeps_its_namespaced_prefix():
    """Widening the digest must not change the logical key's components."""
    key = build_idempotency_key(_payload(), _ctx())
    prefix, digest = key.rsplit(":", 1)
    assert prefix == f"odoo:plasticos:plasticos.enrichment.run:{RUN_ID}"
    assert len(digest) == 32


def test_idempotency_key_ignores_dict_insertion_order():
    """Canonical serialization sorts keys, so key order is not part of identity."""
    a = {"entity": {"id": ENTITY_REF, "name": "Acme"}, "object_type": "plasticos"}
    b = {"object_type": "plasticos", "entity": {"name": "Acme", "id": ENTITY_REF}}
    assert build_idempotency_key(a, _ctx()) == build_idempotency_key(b, _ctx())


# ── PATCH 10 — Gate_SDK owns the packet ───────────────────────────────────


def test_packet_is_built_by_the_sdk_with_the_canonical_action():
    """The SDK builds the packet from business inputs; Odoo supplies no transport.

    Previously this test called ``create_transport_packet`` itself, which meant
    it asserted a packet Odoo built. Odoo no longer builds one: the contract is
    now that ``GateClient.execute(action=..., payload=...)`` produces the same
    canonical header from business inputs alone. We capture the packet the SDK
    constructs by stubbing the one transport method underneath ``execute``.
    """
    sdk = pytest.importorskip(
        "constellation_node_sdk",
        reason="Gate SDK is an Odoo.sh runtime dependency; absent from the pure-Python tier",
    )
    if not hasattr(sdk.GateClient, "execute"):
        pytest.skip(
            "installed constellation_node_sdk predates GateClient.execute(); "
            "bump the constellation-node-sdk pin in requirements.txt"
        )
    payload = _payload()
    ctx = _ctx()

    captured = {}

    async def _capture(self, packet):
        captured["packet"] = packet
        return packet

    client = sdk.GateClient(sdk.GateClientConfig(gate_url="https://gate.invalid", local_node="odoo"))
    # Stub the single transport method `execute` delegates to. Everything above
    # it — packet construction, destination, identity, deadline — still runs.
    client.send_to_gate = _capture.__get__(client, type(client))
    asyncio.run(
        client.execute(
            action="converge",
            payload=payload,
            tenant={"actor": "plasticos", "org_id": "plasticos"},
            correlation_id=ctx["correlation_id"],
            classification="internal",
            compliance_tags=("ERP", "ENRICHMENT"),
            idempotency_key=build_idempotency_key(payload, ctx),
            timeout_ms=30_000,
        )
    )
    packet = captured["packet"]
    header = packet.model_dump()["header"]
    # The SDK, not Odoo, chose these: Gate is the only destination it will emit.
    assert header["destination_node"] == "gate"
    assert header["source_node"] == "odoo"
    assert header["action"] == "converge"
    assert header["correlation_id"] == f"plasticos.enrichment.run:{RUN_ID}"
    assert header["timeout_ms"] == 30_000
    assert header["idempotency_key"].startswith("odoo:plasticos:plasticos.enrichment.run:7:")
    # The domain payload rides unchanged; Gate is transport, not a translator.
    assert packet.payload["entity"]["id"] == ENTITY_REF


# ── PATCH 5 — the caller budget is one value, and it has a ceiling ────────


class _FakeIcp:
    """Minimal ir.config_parameter stand-in: sudo() -> self, get_param -> dict."""

    def __init__(self, params: dict[str, str]):
        self._params = params

    def sudo(self):
        return self

    def get_param(self, key, default=None):
        return self._params.get(key, default)


class _TimeoutEnv:
    def __init__(self, raw=None):
        params = {} if raw is None else {"plasticos.gate.timeout_seconds": raw}
        self._icp = _FakeIcp(params)

    def __getitem__(self, model):
        assert model == "ir.config_parameter"
        return self._icp


def test_caller_budget_falls_back_to_thirty_seconds_when_unset():
    assert resolve_gate_timeout_seconds(_TimeoutEnv()) == DEFAULT_GATE_TIMEOUT_SECONDS
    assert DEFAULT_GATE_TIMEOUT_SECONDS == 30.0


def test_caller_budget_accepts_the_seeded_default():
    assert resolve_gate_timeout_seconds(_TimeoutEnv("30")) == 30.0


def test_caller_budget_accepts_the_ceiling_exactly():
    assert resolve_gate_timeout_seconds(_TimeoutEnv(str(MAX_GATE_TIMEOUT_SECONDS))) == MAX_GATE_TIMEOUT_SECONDS


def test_caller_budget_accepts_a_shorter_budget():
    """Configuration may tighten the budget; only widening it is an error."""
    assert resolve_gate_timeout_seconds(_TimeoutEnv("5.5")) == 5.5


@pytest.mark.parametrize("raw", ["30.001", "31", "120", "3600"])
def test_caller_budget_rejects_anything_above_the_ceiling(raw):
    """Rejected, not clamped: min(configured, 30) would be configuration fiction."""
    with pytest.raises(GateIntegrationError) as excinfo:
        resolve_gate_timeout_seconds(_TimeoutEnv(raw))
    assert "30" in str(excinfo.value)
    assert excinfo.value.failure_class == "permanent"


@pytest.mark.parametrize("raw", ["0", "0.0", "-1", "-30"])
def test_caller_budget_rejects_non_positive_values(raw):
    with pytest.raises(GateIntegrationError):
        resolve_gate_timeout_seconds(_TimeoutEnv(raw))


@pytest.mark.parametrize("raw", ["thirty", "30s", "", "  "])
def test_caller_budget_rejects_or_defaults_unparseable_values(raw):
    """Blank falls back to the default; a non-numeric string is a config error."""
    if raw.strip():
        with pytest.raises(GateIntegrationError):
            resolve_gate_timeout_seconds(_TimeoutEnv(raw))
    else:
        assert resolve_gate_timeout_seconds(_TimeoutEnv(raw)) == DEFAULT_GATE_TIMEOUT_SECONDS


@pytest.mark.parametrize("raw", ["inf", "Infinity", "-inf", "nan", "NaN"])
def test_caller_budget_rejects_non_finite_values(raw):
    """float() parses these; `nan > 30` is False, so an explicit isfinite check is required."""
    with pytest.raises(GateIntegrationError):
        resolve_gate_timeout_seconds(_TimeoutEnv(raw))


def test_packet_budget_is_derived_from_the_same_validated_value():
    """The HTTP budget and the advertised packet budget read one config object.

    `send_action` builds the config once and uses `config.timeout_seconds` for
    both `GateClient(config)` and the `timeout_ms` passed to `execute`; there is
    no second parse and no literal, so the two cannot diverge through the
    supported builder path. Post-migration the SDK tightens this further: it
    derives the network deadline from the same header value it advertises.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "timeout_ms=int(float(config.timeout_seconds) * 1000)" in src
    assert "GateClient(config)" in src
    # The budget is handed to the SDK entry point, not to a hand-built packet.
    assert "client.execute(" in src
    assert "create_transport_packet" not in src
    # No second, unvalidated read of the ICP timeout anywhere in the client.
    assert "plasticos.gate.timeout_seconds" not in src


def test_node_identity_has_a_single_source():
    """`local_node` comes off the config the SDK uses, not a second ICP read.

    The SDK derives `source_node` and `reply_to` from `config.local_node`. If
    the bridge also read `plasticos.gate.local_node` from ir.config_parameter
    and normalized it independently, the originator Odoo reports in the tenant
    context could drift from the identity actually on the wire.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "local_node = config.local_node" in src
    # The *read* must be absent, not every mention — the rationale comment names
    # the parameter on purpose.
    assert 'get_param("plasticos.gate.local_node")' not in src


# ── transport failures must stay diagnosable ──────────────────────────────


def test_empty_transport_failure_message_falls_back_to_the_exception_type():
    """A timeout stringifies to "" — the durable record must not be blank.

    Measured on a real Gate transport: an exhausted caller budget raises httpx
    `ConnectTimeout` with `str(exc) == ""`, so the operator saw
    "Gate enrichment failed (retryable): " and the enrichment run stored
    validation_issues=[""]. Right classification, no reason.
    """
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "detail = str(exc) or type(exc).__name__" in src
    assert "raise GateIntegrationError(detail," in src
    assert "raise GateIntegrationError(str(exc)," not in src


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TimeoutError(), "TimeoutError"),
        (ConnectionError(), "ConnectionError"),
        (ValueError("a real message"), "a real message"),
    ],
)
def test_failure_detail_is_never_blank(exc, expected):
    """The fallback rule itself: type name when blank, the message otherwise."""
    assert (str(exc) or type(exc).__name__) == expected


def test_the_ceiling_is_a_single_named_constant():
    """One place to change the budget, so config and packet cannot drift apart."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_config.py").read_text(encoding="utf-8")
    assert src.count("MAX_GATE_TIMEOUT_SECONDS = ") == 1
    assert MAX_GATE_TIMEOUT_SECONDS == 30.0


def test_packet_timeout_header_is_derived_from_the_same_config():
    """The header must not advertise the SDK's fixed 30000 while the client waits
    on a different configured budget."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "timeout_ms=int(float(config.timeout_seconds) * 1000)" in src


def test_odoo_adds_no_retry_loop_around_gate():
    """EIE owns retries; Odoo fails promptly and persists operator state."""
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert "for attempt in range" not in src
    assert "while True" not in src
