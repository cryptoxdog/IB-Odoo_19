"""Enrichment sweep contract (plasticos_gate/services/gate_sweep.py) and its converge v2 results.

Contract authority (read-only): Quantum-L9/Enrichment.Inference.Engine main at
``a606791`` (PR #352), ``docs/contracts/enrichment-sweep.md``. The fixtures
below are the contract's own example shapes (sections 3.1, 3.2, 6.1, 6.2).
Pure Python: no Odoo runtime, no Gate, no network.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plasticos_gate.services import gate_allowlists as allow  # noqa: E402
from plasticos_gate.services import gate_client  # noqa: E402
from plasticos_gate.services.gate_builders import build_sweep_candidate  # noqa: E402
from plasticos_gate.services.gate_contracts import CONVERGE_RESPONSE_V2, CartridgePin, thaw  # noqa: E402
from plasticos_gate.services.gate_mappers import (  # noqa: E402
    V2_PLAN_WRITE,
    V2_SKIP_UNMAPPED,
    parse_sweep_converge_response_v2,
    plan_sweep_converge_v2_writeback,
)
from plasticos_gate.services.gate_sweep import (  # noqa: E402
    CONTRACT_REF,
    REFUSAL_CODES,
    REJECT_REASONS,
    SKIP_REASONS,
    SWEEP_ACTION,
    SWEEP_ACTIONS,
    SWEEP_RESULTS_ACTION,
    SweepCandidate,
    SweepContractError,
    SweepRequest,
    SweepResultsRequest,
    build_sweep_idempotency_key,
    parse_sweep_results_page,
    parse_sweep_send_reply,
    refusal_code,
)

E1, E2, E3 = "res.partner:11", "res.partner:12", "res.partner:13"
SWEEP_ID = "0123456789abcdef0123456789abcdef"
SHA = "590f0fdb6ce1181b4a716f3e00512bf5425ba42d266208aa4dab18afca8dafdb"
PIN = CartridgePin("plasticos", "0.6.0", SHA)


def _request(*ids):
    return SweepRequest(
        tuple(SweepCandidate(entity_id=i, entity={"process_type": "injection"}) for i in ids),
        2.5,
        "odoo:enrichment-sweep:t:2026-11-15:abc",
    )


def _page(**overrides):
    """Section 6.2 example, with the contract's members exactly."""
    page = {
        "sweep_id": SWEEP_ID,
        "state": "running",
        "results": [{"entity_id": E1, "response": {"contract_version": CONVERGE_RESPONSE_V2}}],
        "next_cursor": "1",
        "budget": {"effective_usd": 2.5, "spent_usd": 2.0, "remaining_usd": 0.5},
        "skipped": [{"entity_id": E2, "reason": "budget_exhausted"}],
        "stats": {"enriched": 2, "targets_dropped_undeclared": 0, "budget_exhausted": 1},
    }
    page.update(overrides)
    return page


# ── actions, citation, admission ──────────────────────────────────────────


def test_contract_is_cited_and_actions_are_named():
    assert CONTRACT_REF.endswith("@a606791:docs/contracts/enrichment-sweep.md")
    assert SWEEP_ACTIONS == (SWEEP_ACTION, SWEEP_RESULTS_ACTION) == ("enrichment-sweep", "enrichment-sweep-results")
    assert gate_client._ODOO_REQUIRED_ACTIONS == ("match", "converge")


def test_admission_receipts_are_keyed_by_the_full_action_set():
    config = SimpleNamespace(gate_url="https://g", local_node="odoo", signing_key_id="k")
    assert gate_client._admission_key(config, "t") == ("https://g", "odoo", "k", "t", ("match", "converge"))
    assert gate_client._admission_key(config, "t", SWEEP_ACTIONS)[-1] == ("match", "converge", *SWEEP_ACTIONS)


# ── section 3.1: request ──────────────────────────────────────────────────


def test_send_request_serializes_exactly_the_contract_members():
    body = _request(E1, E2).to_dict()
    assert set(body) == {"candidates", "daily_budget_usd", "idempotency_key"}
    assert body["daily_budget_usd"] == 2.5
    assert body["candidates"][0] == {"entity_id": E1, "node_label": "Facility", "entity": {"process_type": "injection"}}


def test_candidate_carries_field_confidences_only_when_given():
    cand = SweepCandidate(entity_id=E1, entity={}, field_confidences={"process_type": 0.7})
    assert cand.to_dict()["field_confidences"] == {"process_type": 0.7}
    with pytest.raises(SweepContractError):
        SweepCandidate(entity_id=E1, entity={}, field_confidences={"process_type": 1.5})


@pytest.mark.parametrize("bad", ["res.partner:0", "res.partner:abc", "plasticos.facility.profile:1", "11", ""])
def test_candidate_entity_id_is_locked_to_res_partner(bad):
    with pytest.raises(SweepContractError):
        SweepCandidate(entity_id=bad, entity={})


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf"), True])
def test_request_refuses_a_non_positive_or_non_finite_budget(budget):
    with pytest.raises(SweepContractError):
        SweepRequest((SweepCandidate(entity_id=E1, entity={}),), budget, "k")


def test_request_has_no_odoo_budget_ceiling():
    """Section 4: EIE caps the budget with L9_SWEEP_MAX_DAILY_BUDGET_USD; Odoo only requires > 0."""
    assert SweepRequest((SweepCandidate(entity_id=E1, entity={}),), 1000.0, "k").daily_budget_usd == 1000.0


def test_request_refuses_empty_or_duplicate_candidates():
    with pytest.raises(SweepContractError):
        SweepRequest((), 5.0, "k")
    with pytest.raises(SweepContractError):
        _request(E1, E1)


def test_idempotency_key_is_deterministic_and_order_free():
    a = build_sweep_idempotency_key("tenant", "2026-11-15", [E2, E1])
    assert a == build_sweep_idempotency_key("tenant", "2026-11-15", [E1, E2])
    assert a != build_sweep_idempotency_key("tenant", "2026-11-16", [E1, E2])
    assert a != build_sweep_idempotency_key("tenant", "2026-11-15", [E1])


# ── section 6.1: cursor omitted on the first page ─────────────────────────


def test_results_request_omits_cursor_until_there_is_a_next_cursor():
    assert SweepResultsRequest(SWEEP_ID).to_dict() == {"sweep_id": SWEEP_ID}
    assert SweepResultsRequest(SWEEP_ID, "50").to_dict() == {"sweep_id": SWEEP_ID, "cursor": "50"}
    with pytest.raises(SweepContractError):
        SweepResultsRequest("")
    with pytest.raises(SweepContractError):
        SweepResultsRequest(SWEEP_ID, "")


# ── section 3.2: immediate reply ──────────────────────────────────────────


def test_send_reply_example_shape():
    reply = parse_sweep_send_reply(
        {"sweep_id": SWEEP_ID, "accepted": [E1, E2], "rejected": [{"entity_id": E3, "reason": "node_not_declared"}]},
        request=_request(E1, E2, E3),
    )
    assert (reply.sweep_id, reply.accepted, reply.accepted_count, reply.rejected_count) == (SWEEP_ID, (E1, E2), 2, 1)
    assert reply.rejected[0].reason == "node_not_declared"


@pytest.mark.parametrize("reason", sorted(REJECT_REASONS))
def test_every_contract_rejection_reason_is_accepted(reason):
    reply = parse_sweep_send_reply(
        {"sweep_id": SWEEP_ID, "accepted": [], "rejected": [{"entity_id": E1, "reason": reason}]},
        request=_request(E1),
    )
    assert reply.rejected[0].reason == reason


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"sweep_id": SWEEP_ID, "accepted": []},
        {"sweep_id": SWEEP_ID, "accepted": [], "rejected": [], "error": "x"},
        {"sweep_id": "", "accepted": [], "rejected": []},
        {"sweep_id": SWEEP_ID, "accepted": 2, "rejected": 0},
        {"sweep_id": SWEEP_ID, "accepted": [{"entity_id": E1}], "rejected": []},
        {"sweep_id": SWEEP_ID, "accepted": ["res.partner:99"], "rejected": []},
        {"sweep_id": SWEEP_ID, "accepted": [E1], "rejected": [{"entity_id": E1, "reason": "duplicate_entity_id"}]},
        {"sweep_id": SWEEP_ID, "accepted": [E1, E1], "rejected": []},
        {"sweep_id": SWEEP_ID, "accepted": [], "rejected": [{"entity_id": E1, "reason": "no_reason"}]},
        {"sweep_id": SWEEP_ID, "accepted": [], "rejected": [{"entity_id": E1}]},
    ],
)
def test_send_reply_fails_closed(payload):
    with pytest.raises(SweepContractError):
        parse_sweep_send_reply(payload, request=_request(E1, E2))


# ── section 6.2: results page ─────────────────────────────────────────────


def test_results_page_example_shape():
    page = parse_sweep_results_page(_page(), sweep_id=SWEEP_ID)
    assert page.state == "running" and not page.finished
    assert page.results[0].entity_id == E1
    assert isinstance(page.results[0].response, MappingProxyType)
    assert page.skipped[0].reason == "budget_exhausted"
    assert page.budget_dict() == {"effective_usd": 2.5, "spent_usd": 2.0, "remaining_usd": 0.5}
    assert page.stats_dict() == {"enriched": 2, "targets_dropped_undeclared": 0, "budget_exhausted": 1}


def test_completed_with_null_cursor_is_finished_running_is_not():
    assert parse_sweep_results_page(_page(state="completed", next_cursor=None), sweep_id=SWEEP_ID).finished
    assert not parse_sweep_results_page(_page(state="running", next_cursor=None), sweep_id=SWEEP_ID).finished
    assert not parse_sweep_results_page(_page(state="completed", next_cursor="3"), sweep_id=SWEEP_ID).finished


@pytest.mark.parametrize("reason", sorted(SKIP_REASONS))
def test_every_section_5_skip_reason_is_a_per_candidate_skip(reason):
    page = parse_sweep_results_page(_page(skipped=[{"entity_id": E3, "reason": reason}]), sweep_id=SWEEP_ID)
    assert page.skipped[0].reason == reason


@pytest.mark.parametrize("state", ["budget_exhausted", "failed", "readiness_failed", "sweep_failed", "paused"])
def test_only_running_and_completed_are_states(state):
    with pytest.raises(SweepContractError, match="state"):
        parse_sweep_results_page(_page(state=state), sweep_id=SWEEP_ID)


def test_page_for_another_sweep_is_rejected():
    with pytest.raises(SweepContractError, match="sweep"):
        parse_sweep_results_page(_page(sweep_id="f" * 32), sweep_id=SWEEP_ID)


@pytest.mark.parametrize(
    "overrides",
    [
        {"next_cursor": ""},
        {"next_cursor": 3},
        {"budget": []},
        {"budget": {"spent_usd": "2.0"}},
        {"stats": []},
        {"stats": {"enriched": -1}},
        {"stats": {"enriched": 1.5}},
        {"results": {}},
        {"results": [{"entity_id": E1}]},
        {"results": [{"entity_id": E1, "response": []}]},
        {"results": [{"entity_id": E1, "response": {}, "cost": 1}]},
        {"results": [{"entity_id": E1, "response": {}}, {"entity_id": E1, "response": {}}]},
        {"skipped": [{"entity_id": E1}]},
        {"skipped": [{"entity_id": E1, "reason": "not_a_reason"}]},
    ],
)
def test_results_page_fails_closed(overrides):
    with pytest.raises(SweepContractError):
        parse_sweep_results_page(_page(**overrides), sweep_id=SWEEP_ID)


def test_results_page_refuses_unknown_and_missing_members():
    with pytest.raises(SweepContractError, match="unknown"):
        parse_sweep_results_page({**_page(), "debug": True}, sweep_id=SWEEP_ID)
    payload = _page()
    del payload["stats"]
    with pytest.raises(SweepContractError, match="missing"):
        parse_sweep_results_page(payload, sweep_id=SWEEP_ID)


# ── section 7: refusals ───────────────────────────────────────────────────


@pytest.mark.parametrize("code", REFUSAL_CODES)
def test_refusal_codes_are_classified_from_the_failure_message(code):
    assert refusal_code(f"{code}: detail") == code
    assert refusal_code(f"Gate execute failed: {code}: detail") == code


def test_a_transport_failure_carries_no_refusal_code():
    assert refusal_code("TimeoutError") is None
    assert refusal_code("") is None
    assert refusal_code(None) is None


# ── section 3.4 step 5: the converge v2 body EIE stores, parsed with no Odoo request ──


def _fd(name, ftype, **kw):
    return allow.OdooFieldDef(name, ftype, **kw)


FACILITY_FIELD_DEFS = (
    _fd("partner_id", "many2one", relation="res.partner"),
    _fd("contamination_tolerance_pct", "float"),
    _fd("capacity_lbs_month", "integer"),
    _fd("freeform_notes", "text"),
)


def _decl(name):
    return thaw(allow.cartridge_vocabulary("0.6.0").declarations[name])


def _evidence(entity_id, specs):
    identity = {"subject_ref": entity_id, "subject_type": None, "role": None}
    out = {}
    for name, spec in specs.items():
        entry = {
            "state": spec["state"],
            "admitted": spec.get("admitted", False),
            "confidence": None,
            "sources": [],
            "derivation": None,
            "identity": identity,
            "declaration": _decl(name),
            "conflict": None,
            "unknown_reason": None,
        }
        if spec["state"] == "unknown":
            entry["unknown_reason"] = "no_evidence"
        else:
            entry["value"] = spec["value"]
            entry["confidence"] = 0.9
            entry["unit_status"] = "stated" if "unit" in spec else "not_applicable"
            if "unit" in spec:
                entry["unit"] = spec["unit"]
            entry["sources"] = [
                {"source_type": "provider", "source_ref": "r:1", "method": "provider_reply", "independent": None}
            ]
        out[name] = entry
    return out


def _converge_body(entity_id=E1, pin=PIN, node="Facility", specs=None):
    specs = specs or {
        "contamination_tolerance": {"state": "external_claim", "admitted": True, "value": 2.0, "unit": "percent"},
        "freeform_notes": {"state": "unknown"},
    }
    evidence = _evidence(entity_id, specs)
    admitted = {n: s["value"] for n, s in specs.items() if s.get("admitted")}
    return {
        "contract_version": CONVERGE_RESPONSE_V2,
        "state": "completed",
        "failure_reason": None,
        "fields": admitted,
        "confidence": 0.9,
        "resolution": {
            "cartridge_id": pin.id,
            "cartridge_version": pin.version,
            "cartridge_sha256": pin.sha256,
            "node": node,
        },
        "field_evidence": evidence,
        "proposals": [],
    }


def _union():
    return allow.derive_facility_profile_target_all_subjects(FACILITY_FIELD_DEFS, version="0.6.0")


def test_union_target_covers_every_subject_with_the_interactive_rows():
    spec, _unmapped = _union()
    subjects = sorted(set(allow.cartridge_vocabulary("0.6.0").subjects.values()))
    for subject in subjects:
        single = allow.derive_facility_profile_target(FACILITY_FIELD_DEFS, subject=subject, version="0.6.0")[0]
        for row in single.rows:
            assert spec.row(row.cartridge_field) == row
    assert spec.row("min_density") is None
    assert spec.row("contamination_tolerance") and spec.row("capacity_tons_month")


def test_sweep_result_is_validated_against_its_resolution_echo_and_the_candidate():
    parsed = parse_sweep_converge_response_v2(_converge_body(), entity_id=E1, pin=PIN)
    assert parsed.usable, parsed.rejection
    spec, unmapped = _union()
    plan = plan_sweep_converge_v2_writeback(parsed, spec, unmapped)
    assert plan.rejection is None
    by = {d.cartridge_field: d for d in plan.decisions}
    assert by["contamination_tolerance"].action == V2_PLAN_WRITE
    assert by["contamination_tolerance"].odoo_field == "contamination_tolerance_pct"
    assert by["freeform_notes"].skip_reason == "unknown"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["resolution"].update(cartridge_sha256="0" * 64),
        lambda b: b["resolution"].update(cartridge_version="0.5.0"),
        lambda b: b["resolution"].update(cartridge_id="other"),
        lambda b: b["resolution"].update(node="Material"),
    ],
)
def test_a_result_resolved_to_another_pin_or_node_is_rejected(mutate):
    body = _converge_body()
    mutate(body)
    assert not parse_sweep_converge_response_v2(body, entity_id=E1, pin=PIN).usable


def test_a_result_about_another_entity_or_with_a_subject_is_rejected():
    assert not parse_sweep_converge_response_v2(_converge_body(entity_id=E2), entity_id=E1, pin=PIN).usable
    body = _converge_body()
    for entry in body["field_evidence"].values():
        entry["identity"]["subject_type"] = "material"
    assert not parse_sweep_converge_response_v2(body, entity_id=E1, pin=PIN).usable


def test_a_sweep_result_needs_a_sha256_pin():
    unpinned = CartridgePin("plasticos", "0.6.0")
    assert not parse_sweep_converge_response_v2(_converge_body(pin=PIN), entity_id=E1, pin=unpinned).usable


def test_undeclared_or_unmapped_fields_are_skipped_and_recorded():
    specs = {
        "contamination_tolerance": {"state": "external_claim", "admitted": True, "value": 2.0, "unit": "percent"},
        "min_density": {"state": "external_claim", "admitted": True, "value": 0.94, "unit": "g/cm3"},
        "tier": {"state": "external_claim", "admitted": True, "value": "gold"},
    }
    parsed = parse_sweep_converge_response_v2(_converge_body(specs=specs), entity_id=E1, pin=PIN)
    assert parsed.usable, parsed.rejection
    spec, unmapped = _union()
    plan = plan_sweep_converge_v2_writeback(parsed, spec, unmapped)
    by = {d.cartridge_field: d for d in plan.decisions}
    assert by["tier"].skip_reason == V2_SKIP_UNMAPPED and by["tier"].odoo_field == ""
    assert by["min_density"].skip_reason == V2_SKIP_UNMAPPED
    assert by["min_density"].detail == allow.ADR134_RETIRED_REASON
    assert [d.cartridge_field for d in plan.writes] == ["contamination_tolerance"]


def test_a_non_completed_or_v1_result_writes_nothing():
    spec, unmapped = _union()
    for body in ({**_converge_body(), "state": "degraded"}, {"state": "completed"}):
        parsed = parse_sweep_converge_response_v2(copy.deepcopy(body), entity_id=E1, pin=PIN)
        plan = plan_sweep_converge_v2_writeback(parsed, spec, unmapped)
        assert plan.rejection and not plan.decisions


# ── candidate entity: current values in cartridge field names ─────────────


class _Rec:
    _name = "plasticos.facility.profile"
    id = 7

    def __init__(self, **values):
        self._fields = {d.name: d for d in FACILITY_FIELD_DEFS}
        self._values = values
        self.partner_id = SimpleNamespace(id=11)

    def __getitem__(self, key):
        return self._values.get(key)


def test_candidate_entity_holds_the_current_values_of_every_subject():
    spec, _unmapped = _union()
    cand = build_sweep_candidate(
        _Rec(contamination_tolerance_pct=2.0, capacity_lbs_month=2000, freeform_notes="x"), spec
    )
    assert cand.entity_id == E1 and cand.node_label == "Facility"
    assert cand.entity["contamination_tolerance"] == 2.0
    assert "min_density" not in cand.entity, "a retired field is not sent"
