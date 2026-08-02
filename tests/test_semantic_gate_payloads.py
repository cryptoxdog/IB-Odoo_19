"""TASK-027: semantic Gate payload builders — fixtures + egress safety."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plasticos_gate.services.semantic_payloads import (  # noqa: E402
    SemanticPayloadError,
    build_buyer_demand_payload,
    build_match_query_from_demand,
    build_match_query_from_supply,
    build_supply_opportunity_payload,
)

EXAMPLES = ROOT / "contracts" / "schemas" / "examples"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from opportunity_protocol import validate_buyer_demand_payload, validate_supply_payload  # noqa: E402


def _supply_stub(**overrides):
    base = dict(
        id=42,
        state="available",
        specification_id=SimpleNamespace(id=9),
        supplier_partner_id=SimpleNamespace(id=15),
        origin_facility_id=SimpleNamespace(id=18),
        min_lot_size_lbs=38000.0,
        quantity_lbs=40000.0,
        max_lot_size_lbs=44000.0,
        available_from=date(2026, 8, 1),
        available_until=date(2026, 8, 31),
        asking_price_per_lb=0.24,
        currency_id=SimpleNamespace(name="USD"),
        intake_id=SimpleNamespace(id=71),
        source_system="odoo",
        source_record_ref=None,
        contract_version="1.0.0",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _demand_stub(**overrides):
    base = dict(
        id=12,
        state="open",
        specification_id=SimpleNamespace(id=33),
        buyer_partner_id=SimpleNamespace(id=101),
        buyer_facility_id=SimpleNamespace(id=102),
        min_lot_size_lbs=20000.0,
        quantity_lbs=40000.0,
        max_lot_size_lbs=80000.0,
        needed_from=date(2026, 8, 15),
        needed_until=date(2026, 9, 30),
        target_price_per_lb=0.31,
        currency_id=SimpleNamespace(name="USD"),
        source_system="odoo",
        source_record_ref=None,
        contract_version="1.0.0",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_supply_opportunity_validates() -> None:
    payload = build_supply_opportunity_payload(_supply_stub(), revision=3)
    validate_supply_payload(payload)
    assert payload["opportunity_ref"] == "plasticos.supply.opportunity:42"
    assert payload["state"] == "open"
    assert "packet_id" not in payload
    assert "action" not in payload


def test_build_buyer_demand_validates() -> None:
    payload = build_buyer_demand_payload(_demand_stub(), revision=1)
    validate_buyer_demand_payload(payload)
    assert payload["demand_ref"] == "plasticos.buyer.demand:12"
    assert "opportunity_ref" not in payload


def test_reversed_quantity_rejected() -> None:
    with pytest.raises(SemanticPayloadError, match="minimum"):
        build_supply_opportunity_payload(
            _supply_stub(min_lot_size_lbs=50000.0, quantity_lbs=40000.0, max_lot_size_lbs=60000.0),
            revision=1,
        )


def test_reversed_window_rejected() -> None:
    with pytest.raises(SemanticPayloadError, match="need_window"):
        build_buyer_demand_payload(
            _demand_stub(needed_from=date(2026, 10, 1), needed_until=date(2026, 9, 1)),
            revision=1,
        )


def test_match_query_wrappers_have_directions() -> None:
    supply = build_supply_opportunity_payload(_supply_stub(), revision=3)
    demand = build_buyer_demand_payload(_demand_stub(), revision=1)
    s_q = build_match_query_from_supply(supply)
    d_q = build_match_query_from_demand(demand)
    assert s_q["direction"] == "supply_opportunity_to_buyer_facility"
    assert d_q["direction"] == "buyer_demand_to_supply_opportunity"
    assert "packet_id" not in s_q
    assert "packet_id" not in d_q


def test_example_fixtures_still_valid() -> None:
    validate_supply_payload(json.loads((EXAMPLES / "supply-opportunity.json").read_text()))
    validate_buyer_demand_payload(json.loads((EXAMPLES / "buyer-demand.json").read_text()))


def test_transport_fields_rejected_if_smuggled() -> None:
    payload = build_supply_opportunity_payload(_supply_stub(), revision=1)
    payload["packet_id"] = "nope"
    with pytest.raises(SemanticPayloadError, match="transport"):
        build_match_query_from_supply(payload)
