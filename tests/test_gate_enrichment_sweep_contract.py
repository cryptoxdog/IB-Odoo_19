"""Enrichment sweep contract codec (plasticos_gate/services/gate_sweep.py).

Pure Python: no Odoo runtime, no Gate, no network. The EIE contract document
was not published when this was written; these tests pin the ASSUMED shape
(``SWEEP_CONTRACT_ASSUMPTIONS``) and, above all, that every parser fails closed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plasticos_gate.services import gate_client  # noqa: E402
from plasticos_gate.services.gate_builders import build_sweep_candidate  # noqa: E402
from plasticos_gate.services.gate_contracts import CartridgePin, ConvergeRequestV2, freeze  # noqa: E402
from plasticos_gate.services.gate_sweep import (  # noqa: E402
    SWEEP_ACTION,
    SWEEP_ACTIONS,
    SWEEP_CONTRACT_ASSUMPTIONS,
    SWEEP_RESULTS_ACTION,
    SWEEP_STATE_COMPLETED,
    SweepCandidate,
    SweepContractError,
    SweepRequest,
    SweepResultsRequest,
    build_sweep_idempotency_key,
    parse_sweep_results_page,
    parse_sweep_send_reply,
    partner_id_of,
)

E1, E2, E3 = "res.partner:11", "res.partner:12", "res.partner:13"


def _request(*ids):
    return SweepRequest(
        tuple(SweepCandidate(entity_id=i, entity={"process_type": "injection"}) for i in ids),
        5.0,
        "odoo:enrichment-sweep:t:2026-11-15:abc",
    )


def _page(**overrides):
    page = {
        "state": "completed",
        "results": [{"entity_id": E1, "response": {"contract_version": "eie.converge.response/v2"}}],
        "next_cursor": None,
        "budget": {"spent_usd": 1.25, "cap_usd": 5.0},
        "skipped": [{"entity_id": E2, "reason": "budget_exhausted"}],
    }
    page.update(overrides)
    return page


# ── actions and request shapes ────────────────────────────────────────────


def test_sweep_actions_are_named_and_never_widen_interactive_admission():
    assert SWEEP_ACTIONS == (SWEEP_ACTION, SWEEP_RESULTS_ACTION) == ("enrichment-sweep", "enrichment-sweep-results")
    assert gate_client._ODOO_REQUIRED_ACTIONS == ("match", "converge")
    assert SWEEP_CONTRACT_ASSUMPTIONS, "every assumed contract detail is recorded"


def test_admission_receipts_are_keyed_by_the_full_action_set():
    config = type("C", (), {"gate_url": "https://g", "local_node": "odoo", "signing_key_id": "k"})()
    plain = gate_client._admission_key(config, "t")
    sweep = gate_client._admission_key(config, "t", SWEEP_ACTIONS)
    assert plain != sweep, "a sweep grant never vouches for, or blocks, the interactive admission"


def test_send_request_serializes_exactly_the_contract_members():
    body = _request(E1, E2).to_dict()
    assert set(body) == {"candidates", "daily_budget_usd", "idempotency_key"}
    assert body["daily_budget_usd"] == 5.0
    assert body["candidates"][0] == {
        "entity_id": E1,
        "node_label": "Facility",
        "entity": {"process_type": "injection"},
    }


def test_candidate_carries_field_confidences_only_when_given():
    cand = SweepCandidate(entity_id=E1, entity={}, field_confidences={"process_type": 0.9})
    assert cand.to_dict()["field_confidences"] == {"process_type": 0.9}
    with pytest.raises(SweepContractError):
        SweepCandidate(entity_id=E1, entity={}, field_confidences={"process_type": 1.5})


@pytest.mark.parametrize("bad", ["res.partner:0", "res.partner:abc", "plasticos.facility.profile:1", "11", ""])
def test_candidate_entity_id_is_locked_to_res_partner(bad):
    with pytest.raises(SweepContractError):
        SweepCandidate(entity_id=bad, entity={})


def test_candidate_node_label_is_facility_only():
    with pytest.raises(SweepContractError):
        SweepCandidate(entity_id=E1, entity={}, node_label="Material")


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf"), True])
def test_request_refuses_a_non_positive_or_non_finite_budget(budget):
    with pytest.raises(SweepContractError):
        SweepRequest((SweepCandidate(entity_id=E1, entity={}),), budget, "k")


def test_request_refuses_empty_or_duplicate_candidates():
    with pytest.raises(SweepContractError):
        SweepRequest((), 5.0, "k")
    with pytest.raises(SweepContractError):
        _request(E1, E1)


def test_results_request_first_page_has_null_cursor():
    assert SweepResultsRequest("sw-1").to_dict() == {"sweep_id": "sw-1", "cursor": None}
    with pytest.raises(SweepContractError):
        SweepResultsRequest("")


def test_idempotency_key_is_deterministic_and_order_free():
    a = build_sweep_idempotency_key("tenant", "2026-11-15", [E2, E1])
    b = build_sweep_idempotency_key("tenant", "2026-11-15", [E1, E2])
    assert a == b and a.startswith("odoo:enrichment-sweep:tenant:2026-11-15:")
    assert a != build_sweep_idempotency_key("tenant", "2026-11-16", [E1, E2])
    assert a != build_sweep_idempotency_key("other", "2026-11-15", [E1, E2])
    assert a != build_sweep_idempotency_key("tenant", "2026-11-15", [E1])
    with pytest.raises(SweepContractError):
        build_sweep_idempotency_key("tenant", "15/11/2026", [E1])


def test_partner_id_of():
    assert partner_id_of(E1) == 11
    with pytest.raises(SweepContractError):
        partner_id_of("res.users:1")


# ── send reply ────────────────────────────────────────────────────────────


def test_send_reply_with_lists():
    reply = parse_sweep_send_reply(
        {"sweep_id": "sw-1", "accepted": [E1, {"entity_id": E2}], "rejected": [{"entity_id": E3, "reason": "x"}]},
        request=_request(E1, E2, E3),
    )
    assert (reply.sweep_id, reply.accepted_count, reply.rejected_count) == ("sw-1", 2, 1)
    assert reply.accepted == (E1, E2)
    assert reply.rejected[0].reason == "x"


def test_send_reply_with_counts():
    reply = parse_sweep_send_reply({"sweep_id": "sw-1", "accepted": 2, "rejected": 0}, request=_request(E1, E2))
    assert (reply.accepted_count, reply.rejected_count) == (2, 0)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {"sweep_id": "sw", "accepted": []},
        {"sweep_id": "sw", "accepted": [], "rejected": [], "error": "x"},
        {"sweep_id": "", "accepted": [], "rejected": []},
        {"sweep_id": "sw", "accepted": ["res.partner:99"], "rejected": []},
        {"sweep_id": "sw", "accepted": [E1], "rejected": [{"entity_id": E1, "reason": "x"}]},
        {"sweep_id": "sw", "accepted": 5, "rejected": 0},
        {"sweep_id": "sw", "accepted": True, "rejected": 0},
        {"sweep_id": "sw", "accepted": [{"entity_id": E1, "extra": 1}], "rejected": []},
        {"sweep_id": "sw", "accepted": [], "rejected": [{"entity_id": E1}]},
    ],
)
def test_send_reply_fails_closed(payload):
    with pytest.raises(SweepContractError):
        parse_sweep_send_reply(payload, request=_request(E1, E2))


# ── results pages ─────────────────────────────────────────────────────────


def test_results_page_valid_and_frozen():
    page = parse_sweep_results_page(_page())
    assert page.state == SWEEP_STATE_COMPLETED and page.finished
    assert page.results[0].entity_id == E1
    assert isinstance(page.results[0].response, MappingProxyType)
    assert page.results[0].response_dict() == {"contract_version": "eie.converge.response/v2"}
    assert page.skipped[0].reason == "budget_exhausted"
    assert page.budget_dict() == {"spent_usd": 1.25, "cap_usd": 5.0}


def test_results_page_running_or_with_cursor_is_not_finished():
    assert not parse_sweep_results_page(_page(state="running")).finished
    assert not parse_sweep_results_page(_page(next_cursor="c2")).finished


@pytest.mark.parametrize(
    "overrides",
    [
        {"state": "paused"},
        {"state": None},
        {"next_cursor": ""},
        {"next_cursor": 3},
        {"budget": []},
        {"results": {}},
        {"results": [{"entity_id": E1}]},
        {"results": [{"entity_id": E1, "response": []}]},
        {"results": [{"entity_id": "res.partner:x", "response": {}}]},
        {"results": [{"entity_id": E1, "response": {}, "cost": 1}]},
        {"results": [{"entity_id": E1, "response": {}}, {"entity_id": E1, "response": {}}]},
        {"skipped": [{"entity_id": E1}]},
        {"skipped": {}},
    ],
)
def test_results_page_fails_closed(overrides):
    with pytest.raises(SweepContractError):
        parse_sweep_results_page(_page(**overrides))


def test_results_page_refuses_unknown_and_missing_members():
    with pytest.raises(SweepContractError, match="unknown"):
        parse_sweep_results_page({**_page(), "debug": True})
    payload = _page()
    del payload["skipped"]
    with pytest.raises(SweepContractError, match="missing"):
        parse_sweep_results_page(payload)
    with pytest.raises(SweepContractError):
        parse_sweep_results_page("not an object")


# ── candidate from the v2 request it stands for ───────────────────────────


def test_candidate_entity_is_the_requests_current_values_in_cartridge_names():
    request = ConvergeRequestV2(
        cartridge=CartridgePin("plasticos", "0.6.0"),
        node="Facility",
        subject_type="material",
        subject_role="buyer",
        targets=freeze([{"field": "min_density", "type": {"type": "float"}}]),
        observations=freeze(
            [
                {"field": "processed_polymers", "value": [{"code": "hdpe"}], "source_kind": "odoo_record"},
                {"field": "max_density", "value": 0.97, "unit": "g/cm3", "source_kind": "odoo_record"},
            ]
        ),
        entity=freeze({"id": E1, "name": "Buyer"}),
        object_type="res.partner",
        objective="x",
        max_variations=1,
        consensus_threshold=0.8,
    )
    cand = build_sweep_candidate(request)
    assert cand.entity_id == E1 and cand.node_label == "Facility"
    assert cand.to_dict()["entity"] == {"processed_polymers": [{"code": "hdpe"}], "max_density": 0.97}
    assert "min_density" not in cand.entity, "an empty field is a target, never a current value"
