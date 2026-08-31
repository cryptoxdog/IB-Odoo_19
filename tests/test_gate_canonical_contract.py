"""Canonical Gate contract: Odoo emits EnrichRequest, consumes EnrichResponse.

The rail this pins:

    Odoo build_converge_request
      -> Gate_SDK create_transport_packet (action="converge")
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

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import (  # noqa: E402
    build_converge_request,
    build_idempotency_key,
    build_odoo_context,
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
    src = (ROOT / "plasticos_gate" / "services" / "gate_client.py").read_text(encoding="utf-8")
    assert 'destination_node="gate"' in src


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


# ── PATCH 10 — Gate_SDK owns the packet ───────────────────────────────────


def test_packet_is_built_by_the_sdk_with_the_canonical_action():
    """Observable behaviour through the SDK-facing adapter; no SDK internals here."""
    sdk = pytest.importorskip(
        "constellation_node_sdk",
        reason="Gate SDK is an Odoo.sh runtime dependency; absent from the pure-Python tier",
    )
    payload = _payload()
    ctx = _ctx()
    packet = sdk.create_transport_packet(
        action="converge",
        payload=payload,
        tenant={"actor": "plasticos", "org_id": "plasticos"},
        source_node="odoo",
        destination_node="gate",
        reply_to="odoo",
        correlation_id=ctx["correlation_id"],
        classification="internal",
        compliance_tags=("ERP", "ENRICHMENT"),
        idempotency_key=build_idempotency_key(payload, ctx),
        timeout_ms=30_000,
    )
    header = packet.model_dump()["header"]
    assert header["action"] == "converge"
    assert header["correlation_id"] == f"plasticos.enrichment.run:{RUN_ID}"
    assert header["timeout_ms"] == 30_000
    assert header["idempotency_key"].startswith("odoo:plasticos:plasticos.enrichment.run:7:")
    # The domain payload rides unchanged; Gate is transport, not a translator.
    assert packet.payload["entity"]["id"] == ENTITY_REF


# ── PATCH 5 — the caller budget is one value, not two ─────────────────────


def test_caller_budget_default_is_thirty_seconds():
    src = (ROOT / "plasticos_gate" / "services" / "gate_config.py").read_text(encoding="utf-8")
    assert 'icp.get_param("plasticos.gate.timeout_seconds") or "30"' in src


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
