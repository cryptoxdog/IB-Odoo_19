"""Repo-level field-contract checks for TASK-025 facility rule/capacity models."""

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


def test_facility_rule_required_ondelete_and_constraint() -> None:
    path = MOD / "models" / "facility_material_rule.py"
    fields = _model_fields(path)
    for name in ("name", "canonical_uuid", "company_id", "facility_profile_id", "rule_type", "contract_version"):
        req = _kw(fields[name], "required")
        assert isinstance(req, ast.Constant) and req.value is True, name
    assert _kw(fields["facility_profile_id"], "ondelete").value == "cascade"
    assert _kw(fields["company_id"], "ondelete").value == "restrict"
    text = path.read_text()
    assert "_sql_constraints" not in text
    assert "models.Constraint" in text
    assert "mail.thread" in text
    assert "PROCESS_SELECTION" in text


def test_capacity_observation_required_and_no_chatter() -> None:
    path = MOD / "models" / "capacity_observation.py"
    fields = _model_fields(path)
    for name in (
        "canonical_uuid",
        "company_id",
        "facility_profile_id",
        "capacity_kind",
        "value",
        "unit_code",
        "value_state",
        "observed_at",
        "source_system",
        "contract_version",
    ):
        req = _kw(fields[name], "required")
        assert isinstance(req, ast.Constant) and req.value is True, name
    assert _kw(fields["facility_profile_id"], "ondelete").value == "cascade"
    text = path.read_text()
    assert "mail.thread" not in text
    assert "_sql_constraints" not in text
    assert "models.Constraint" in text
    assert "<chatter/>" not in (MOD / "views" / "capacity_observation_views.xml").read_text()


def test_acl_covers_facility_and_capacity() -> None:
    rows = list(csv.DictReader((MOD / "security" / "ir.model.access.csv").open()))
    models = {r["model_id:id"] for r in rows}
    assert "model_plasticos_facility_material_rule" in models
    assert "model_plasticos_capacity_observation" in models
