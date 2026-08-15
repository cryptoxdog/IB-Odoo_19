"""Pure-Python contract tests for plasticos_gate match builders, mappers, and config."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.gate_builders import build_converge_request, build_match_request  # noqa: E402
from plasticos_gate.services.gate_config import (  # noqa: E402
    _gate_url_usable,
    gate_auto_writeback_enabled,
    gate_enrichment_enabled,
    gate_matching_enabled,
)
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    extract_audit_metadata,
    map_converge_response,
    map_match_response,
    map_match_response_to_matcher_dicts,
    partner_writeback_from_converge,
)


class _MockICP:
    def __init__(self, params: dict[str, str]):
        self._params = params

    def get_param(self, key: str, default=None):
        return self._params.get(key, default)


class _MockEnv:
    def __init__(self, params: dict[str, str] | None = None):
        self.cr = SimpleNamespace(dbname="testdb")
        self.company = SimpleNamespace(id=1)
        self.user = SimpleNamespace(id=2)
        self._params = params or {}
        self._icp = _MockICP(self._params)

    def __getitem__(self, key: str):
        if key == "ir.config_parameter":
            return self
        raise KeyError(key)

    def sudo(self):
        return self

    def get_param(self, key: str, default=None):
        return self._icp.get_param(key, default)


class _FieldProxy:
    def __init__(self, *, code=None, name=None, record_id=None):
        self.code = code
        self.name = name
        self.id = record_id


class _IntakeStub:
    _name = "plasticos.intake"

    def __init__(self):
        self.id = 42
        self._fields = {
            "polymer_id",
            "form_id",
            "color_id",
            "source_type_id",
            "quantity_per_load_lbs",
            "contamination_pct",
            "mfi_value",
            "lat",
            "lon",
            "partner_id",
        }
        self.polymer_id = _FieldProxy(code="HDPE", name="HDPE", record_id=10)
        self.form_id = _FieldProxy(code="PELLET", name="Pellet", record_id=11)
        self.color_id = _FieldProxy(code="NAT", name="Natural", record_id=12)
        self.source_type_id = _FieldProxy(code="PCR", name="Post Consumer", record_id=13)
        self.quantity_per_load_lbs = 40000.0
        self.contamination_pct = 2.5
        self.mfi_value = 0.8
        self.lat = 35.0
        self.lon = -80.0
        self.partner_id = SimpleNamespace(id=99)

    def __getitem__(self, key):
        return getattr(self, key)


def test_gate_matching_enabled_false_when_url_empty():
    env = _MockEnv({"plasticos.gate.matching_enabled": "1"})
    assert gate_matching_enabled(env) is False


def test_gate_url_rejects_plain_http_by_default():
    """Cleartext HTTP Gate URLs are rejected unless explicitly opted in (S5332)."""
    env = _MockEnv({"plasticos.gate.url": "http://gate.example.com", "plasticos.gate.matching_enabled": "1"})
    assert _gate_url_usable(env["ir.config_parameter"].sudo()) is False
    assert gate_matching_enabled(env) is False


def test_gate_url_allows_http_with_explicit_insecure_opt_in():
    """Local-dev loopback deployments may opt in to plain HTTP explicitly."""
    env = _MockEnv(
        {
            "plasticos.gate.url": "http://127.0.0.1:8080",
            "plasticos.gate.allow_insecure_http": "1",
        }
    )
    assert _gate_url_usable(env["ir.config_parameter"].sudo()) is True


def test_gate_url_accepts_https_without_opt_in():
    env = _MockEnv({"plasticos.gate.url": "https://gate.example.com"})
    assert _gate_url_usable(env["ir.config_parameter"].sudo()) is True


def test_gate_matching_enabled_false_when_flag_off():
    env = _MockEnv(
        {
            "plasticos.gate.url": "https://gate.example.com",
            "plasticos.gate.matching_enabled": "0",
        }
    )
    assert gate_matching_enabled(env) is False


def test_build_match_request_maps_intake_fields():
    env = _MockEnv()
    intake = _IntakeStub()
    request = build_match_request(env, intake=intake, top_n=5, mode="strict")
    assert request.query["polymer_type"] == "HDPE"
    assert request.query["form"] == "PELLET"
    assert request.query["color"] == "NAT"
    assert request.query["quantity_per_load_lbs"] == 40000.0
    assert request.query["contamination_pct"] == 2.5
    assert request.query["intake_id"] == 42
    assert request.query["supplier_partner_id"] == 99
    assert request.query["mode"] == "strict"
    assert request.top_n == 5
    assert request.odoo["model"] == "plasticos.intake"
    assert request.odoo["record_id"] == 42


def test_map_match_response_reads_candidates_and_resolves_entity_ref():
    # DEC-001/OPTION-B: identity comes from entity_ref ("res.partner:<int>"), not a bare id.
    payload = {
        "query_id": "q-42",
        "direction": "intake_to_buyer",
        "candidates": [
            {
                "entity_ref": "res.partner:7",
                "eligible": True,
                "score": 85,
                "score_scale": "0_to_100",
                "rank": 1,
                "failed_gates": ["gate_3"],
                "explanation": "Strong fit",
            }
        ],
        "total_candidates": 1,
        "execution_time_ms": 12,
    }
    mapped = map_match_response(payload)
    assert mapped.unresolved == []
    assert mapped.query_id == "q-42"
    assert mapped.total_candidates == 1
    assert len(mapped.results) == 1
    cand = mapped.results[0]
    assert cand.buyer_partner_id == 7
    assert cand.entity_ref == "res.partner:7"
    assert cand.normalized_score == pytest.approx(0.85)
    rows = map_match_response_to_matcher_dicts(
        mapped,
        audit_metadata={"gate_packet_id": "pkt-1", "gate_correlation_id": "corr-1"},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["buyer_id"] == 7
    assert row["total_score"] == pytest.approx(0.85)
    assert row["match_source"] == "gate"
    assert row["gate_packet_id"] == "pkt-1"
    assert row["gate_correlation_id"] == "corr-1"
    assert row["gates_failed"] == ["gate_3"]


def test_map_match_response_missing_candidates_key_raises():
    # The OLD "results" contract must fail loudly, never silently empty.
    with pytest.raises(KeyError):
        map_match_response({"results": [{"entity_ref": "res.partner:1"}]})


def test_map_match_response_unresolvable_refs_fail_safe():
    payload = {
        "candidates": [
            {"entity_ref": "res.partner:102"},          # ok
            {"entity_ref": "product.product:9"},        # foreign namespace -> skip
            {"entity_ref": 102},                        # bare integer -> skip
            {"entity_ref": "res.partner:not-an-int"},   # non-integer id -> skip
            {},                                         # missing entity_ref -> skip
        ]
    }
    mapped = map_match_response(payload)
    assert [c.buyer_partner_id for c in mapped.results] == [102]
    assert len(mapped.unresolved) == 4
    assert all("entity_ref" in entry for entry in mapped.unresolved)


def test_map_match_response_sorts_by_normalized_score_descending():
    payload = {
        "candidates": [
            {"entity_ref": "res.partner:1", "score": 40, "score_scale": "0_to_100"},
            {"entity_ref": "res.partner:2", "score": 0.95, "score_scale": "0_to_1"},
            {"entity_ref": "res.partner:3", "score": 10, "score_scale": "0_to_100"},
        ]
    }
    mapped = map_match_response(payload)
    assert [c.buyer_partner_id for c in mapped.results] == [2, 1, 3]
    assert mapped.results[0].normalized_score == pytest.approx(0.95)


def test_extract_audit_metadata_reads_packet_header():
    packet = MagicMock()
    packet.header.packet_id = "abc-123"
    packet.header.correlation_id = "corr-xyz"
    audit = extract_audit_metadata(packet)
    assert audit["gate_packet_id"] == "abc-123"
    assert audit["gate_correlation_id"] == "corr-xyz"


# ── Enrichment converge (ROAD-GATE-013) ────────────────────────────────────


class _PartnerStub:
    _name = "res.partner"

    def __init__(self):
        self.id = 55
        self._fields = {"name", "website", "city", "zip", "street", "street2", "comment", "email", "phone"}
        self.name = "Acme Recycling"
        self.website = "https://acme.example"
        self.city = "Charlotte"
        self.zip = "28202"
        self.street = "1 Polymer Way"
        self.street2 = False
        self.comment = False
        self.email = False
        self.phone = False

    def __getitem__(self, key):
        return getattr(self, key)


class _SourceStub:
    def __init__(self, url):
        self.url = url


class _RunStub:
    _name = "plasticos.enrichment.run"

    def __init__(self):
        self.id = 7
        self.partner_id = _PartnerStub()
        self.source_ids = [_SourceStub("https://acme.example/about")]


def test_gate_enrichment_enabled_false_when_url_empty():
    env = _MockEnv({"plasticos.gate.enrichment_enabled": "1"})
    assert gate_enrichment_enabled(env) is False


def test_gate_enrichment_enabled_false_when_flag_off():
    # Live-by-default, but an explicit "0" disables even with URL set
    env = _MockEnv({"plasticos.gate.url": "https://gate.example.com", "plasticos.gate.enrichment_enabled": "0"})
    assert gate_enrichment_enabled(env) is False


def test_gate_auto_writeback_enabled_default_off():
    # No param set → review-only is the default (TASK-002: no auto-write without explicit enablement)
    assert gate_auto_writeback_enabled(_MockEnv()) is False


def test_gate_auto_writeback_enabled_on_when_flag_one():
    # Explicit opt-in re-enables live application
    env = _MockEnv({"plasticos.gate.auto_writeback": "1"})
    assert gate_auto_writeback_enabled(env) is True


def test_gate_auto_writeback_enabled_off_when_flag_zero():
    env = _MockEnv({"plasticos.gate.auto_writeback": "0"})
    assert gate_auto_writeback_enabled(env) is False


def test_gate_icp_seed_auto_writeback_review_only():
    # VAL-002: the install seed must default to review-only (0)
    seed = Path(__file__).resolve().parents[1] / "plasticos_gate/data/gate_icp_seed.xml"
    text = seed.read_text(encoding="utf-8")
    block = text.split('id="param_gate_auto_writeback"', 1)[1].split("</record>", 1)[0]
    assert '<field name="value">0</field>' in block


def test_build_converge_request_maps_partner_snapshot_to_eie_shape():
    env = _MockEnv()
    run = _RunStub()
    request = build_converge_request(env, run)
    assert request.entity["_odoo_entity_id"] == "res.partner:55"
    assert request.entity["name"] == "Acme Recycling"
    assert request.entity["website"] == "https://acme.example"
    assert request.entity["source_urls"] == ["https://acme.example/about"]
    assert request.object_type == "plasticos"
    assert request.objective == "Full entity enrichment and inference"
    assert request.max_variations == 5  # max_passes None -> EIE default
    assert request.odoo["model"] == "plasticos.enrichment.run"
    assert request.odoo["record_id"] == 7
    wire = request.to_dict()
    assert set(wire) >= {"entity", "object_type", "objective", "max_variations", "odoo"}
    assert "_odoo_entity_id" in wire["entity"]


def test_build_converge_request_clamps_max_passes():
    env = _MockEnv()
    run = _RunStub()
    assert build_converge_request(env, run, max_passes=20).max_variations == 10
    assert build_converge_request(env, run, max_passes=0).max_variations == 1


def test_partner_writeback_from_converge_allowlist_only():
    resp = map_converge_response(
        {
            "state": "completed",
            "fields": {
                "website": "https://acme-new.example",
                "city": "Raleigh",
                "supplier_rank": 9,  # not in allowlist -> dropped
                "phone": "",  # empty -> dropped
            },
        }
    )
    vals = partner_writeback_from_converge(resp)
    assert vals == {"website": "https://acme-new.example", "city": "Raleigh"}


def test_map_converge_response_carries_eie_fields_without_fabrication():
    # DNB-006: every EnrichResponse field carried; total_cost_usd/writeback never fabricated.
    payload = {
        "state": "completed",
        "fields": {"website": "https://acme-new.example"},
        "confidence": 0.9,
        "variation_count": 3,
        "pass_count": 2,
        "consensus_threshold": 0.65,
        "uncertainty_score": 0.1,
        "processing_time_ms": 41,
        "quality_tier": "high",
        "inference_version": "v1.2.3",
        "kb_content_hash": "abc123",
        "kb_files_consulted": ["kb/a.md"],
        "kb_fragment_ids": ["frag-1"],
        "inferences": [{"k": "v"}],
        "grade_matches": [{"k": "v"}],
        "enrichment_payload": {"k": "v"},
        "feature_vector": [0.1, 0.2],
        "tokens_used": 512,
        "failure_reason": None,
    }
    resp = map_converge_response(payload)
    assert resp.status == "ok"
    assert resp.state == "completed"
    assert resp.final_fields == {"website": "https://acme-new.example"}
    assert resp.confidence == 0.9
    assert resp.variation_count == 3
    assert resp.pass_count == 2
    assert resp.tokens_used == 512
    assert resp.kb_files_consulted == ["kb/a.md"]
    assert resp.kb_fragment_ids == ["frag-1"]
    assert resp.inferences == [{"k": "v"}]
    assert resp.grade_matches == [{"k": "v"}]
    assert resp.enrichment_payload == {"k": "v"}
    assert resp.feature_vector == [0.1, 0.2]
    assert resp.total_cost_usd is None  # UNAVAILABLE — not fabricated
    assert resp.writeback_applied is None  # UNAVAILABLE — not fabricated


def test_map_converge_response_non_completed_is_not_ok():
    resp = map_converge_response({"state": "failed", "failure_reason": "worker timeout"})
    assert resp.status != "ok"
    assert resp.failure_reason == "worker timeout"
