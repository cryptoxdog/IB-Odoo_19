"""TASK-039: split opportunity protocol — fixtures + cross-field validators."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from opportunity_protocol import (  # noqa: E402
    OpportunityProtocolError,
    assert_not_combined_protocol,
    validate_buyer_demand_payload,
    validate_supply_payload,
)

EXAMPLES = ROOT / "contracts" / "schemas" / "examples"
NEGATIVES = ROOT / "contracts" / "schemas" / "negative_examples"
DRAFT = ROOT / "contracts" / "schemas" / "draft"
MODELS = ROOT / "plasticos_semantic_kernel" / "models"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def test_schemas_exist_as_peer_files() -> None:
    assert (DRAFT / "supply-opportunity.schema.yaml").is_file()
    assert (DRAFT / "buyer-demand.schema.yaml").is_file()
    # No combined opportunity-protocol schema in-repo
    combined = list((ROOT / "contracts").rglob("*opportunity-protocol*"))
    assert combined == []


def test_positive_supply_fixture() -> None:
    validate_supply_payload(_load(EXAMPLES / "supply-opportunity.json"))


def test_positive_buyer_demand_fixture() -> None:
    validate_buyer_demand_payload(_load(EXAMPLES / "buyer-demand.json"))


def test_negative_reversed_quantity() -> None:
    with pytest.raises(OpportunityProtocolError, match="minimum"):
        validate_supply_payload(_load(NEGATIVES / "supply-opportunity-reversed-quantity.json"))


def test_negative_missing_quantity() -> None:
    payload = _load(NEGATIVES / "supply-opportunity-missing-quantity.json")
    with pytest.raises(OpportunityProtocolError):
        validate_supply_payload(payload)


def test_negative_reversed_window() -> None:
    with pytest.raises(OpportunityProtocolError, match="need_window"):
        validate_buyer_demand_payload(_load(NEGATIVES / "buyer-demand-reversed-window.json"))


def test_rejects_combined_discriminator_payload() -> None:
    payload = _load(EXAMPLES / "supply-opportunity.json")
    payload["demand_ref"] = "plasticos.buyer.demand:1"
    with pytest.raises(OpportunityProtocolError, match="mix"):
        assert_not_combined_protocol(payload)


def test_rejects_legacy_discriminator_key() -> None:
    payload = _load(EXAMPLES / "supply-opportunity.json")
    payload["opportunity_type"] = "supply"
    with pytest.raises(OpportunityProtocolError, match="forbidden"):
        validate_supply_payload(payload)


def test_models_have_runtime_cross_field_constraints() -> None:
    for rel in ("supply_opportunity.py", "buyer_demand.py"):
        tree = ast.parse((MODELS / rel).read_text())
        constrains = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") == "constrains":
                        constrains.append(node.name)
        assert "_check_quantity_order" in constrains, rel
        assert "_check_window_order" in constrains, rel
