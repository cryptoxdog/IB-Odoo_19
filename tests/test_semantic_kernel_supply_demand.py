"""Repo-level field-contract checks for TASK-024 supply/demand models."""

from __future__ import annotations

import ast
import csv
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "plasticos_semantic_kernel"


def _model_fields(path: Path) -> dict[str, ast.Call]:
    tree = ast.parse(path.read_text())
    fields: dict[str, ast.Call] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.Assign) and len(item.targets) == 1:
                target = item.targets[0]
                if isinstance(target, ast.Name) and isinstance(item.value, ast.Call):
                    fields[target.id] = item.value
    return fields


def _kw(call: ast.Call, name: str):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def test_supply_opportunity_required_and_ondelete() -> None:
    fields = _model_fields(MOD / "models" / "supply_opportunity.py")
    for name in (
        "name",
        "canonical_uuid",
        "company_id",
        "material_profile_id",
        "supplier_partner_id",
        "state",
        "quantity_state",
        "contract_version",
    ):
        req = _kw(fields[name], "required")
        assert isinstance(req, ast.Constant) and req.value is True, name
    for name, ondelete in [
        ("company_id", "restrict"),
        ("material_profile_id", "restrict"),
        ("supplier_partner_id", "restrict"),
        ("intake_id", "set null"),
        ("specification_id", "restrict"),
        ("currency_id", "restrict"),
    ]:
        od = _kw(fields[name], "ondelete")
        assert isinstance(od, ast.Constant) and od.value == ondelete, (name, ondelete)
    text = (MOD / "models" / "supply_opportunity.py").read_text()
    assert "_sql_constraints" not in text
    assert "models.Constraint" in text
    assert "mail.thread" in text
    assert "score" not in text.lower() or "score" not in text  # no scoring


def test_buyer_demand_required_and_ondelete() -> None:
    fields = _model_fields(MOD / "models" / "buyer_demand.py")
    for name in (
        "name",
        "canonical_uuid",
        "company_id",
        "buyer_partner_id",
        "specification_id",
        "state",
        "quantity_state",
        "contract_version",
    ):
        req = _kw(fields[name], "required")
        assert isinstance(req, ast.Constant) and req.value is True, name
    for name, ondelete in [
        ("company_id", "restrict"),
        ("buyer_partner_id", "restrict"),
        ("specification_id", "restrict"),
        ("currency_id", "restrict"),
        ("delivery_state_id", "restrict"),
    ]:
        od = _kw(fields[name], "ondelete")
        assert isinstance(od, ast.Constant) and od.value == ondelete, (name, ondelete)
    text = (MOD / "models" / "buyer_demand.py").read_text()
    assert "_sql_constraints" not in text
    assert "models.Constraint" in text
    assert "mail.thread" in text


def test_acl_covers_supply_and_demand() -> None:
    rows = list(csv.DictReader((MOD / "security" / "ir.model.access.csv").open()))
    models = {r["model_id:id"] for r in rows}
    assert "model_plasticos_supply_opportunity" in models
    assert "model_plasticos_buyer_demand" in models


def test_no_ambiguous_auto_conversion_helpers() -> None:
    for fname in ("supply_opportunity.py", "buyer_demand.py"):
        text = (MOD / "models" / fname).read_text()
        assert "auto_convert" not in text
        assert "send_to_gate" not in text
        assert "TransportPacket" not in text
