"""Repo-level field-contract checks for TASK-023 semantic kernel models."""

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


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _kw(call: ast.Call, name: str):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _class_attrs(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name):
                            names.add(t.id)
    return names


def test_specification_field_set_and_constraints() -> None:
    path = MOD / "models" / "material_specification.py"
    names = _class_attrs(path)
    for required in (
        "name",
        "canonical_uuid",
        "company_id",
        "status",
        "polymer_id",
        "form_id",
        "contract_version",
        "migration_batch_id",
    ):
        assert required in names
    text = path.read_text()
    assert "canonical_uuid_uniq" in text
    assert "unique(canonical_uuid)" in text
    assert "mail.thread" in text


def test_observation_field_set_and_constraints() -> None:
    path = MOD / "models" / "material_observation.py"
    names = _class_attrs(path)
    for required in (
        "canonical_uuid",
        "company_id",
        "material_profile_id",
        "feature_id",
        "value_state",
        "method",
        "observed_at",
        "source_system",
        "contract_version",
    ):
        assert required in names
    text = path.read_text()
    assert "canonical_uuid_uniq" in text
    assert "mail.thread" not in text


def test_specification_required_and_ondelete() -> None:
    fields = _model_fields(MOD / "models" / "material_specification.py")
    for name in (
        "name",
        "canonical_uuid",
        "company_id",
        "status",
        "version",
        "polymer_id",
        "form_id",
        "contract_version",
    ):
        req = _kw(fields[name], "required")
        assert isinstance(req, ast.Constant) and req.value is True, name
    for name, ondelete in [
        ("company_id", "restrict"),
        ("polymer_id", "restrict"),
        ("form_id", "restrict"),
        ("color_id", "restrict"),
        ("supersedes_id", "restrict"),
        ("legacy_material_profile_id", "set null"),
    ]:
        od = _kw(fields[name], "ondelete")
        assert isinstance(od, ast.Constant) and od.value == ondelete, (name, ondelete)
    assert _call_name(fields["attribute_ids"]) == "Many2many"


def test_observation_required_and_ondelete() -> None:
    fields = _model_fields(MOD / "models" / "material_observation.py")
    for name in (
        "canonical_uuid",
        "company_id",
        "material_profile_id",
        "feature_id",
        "value_state",
        "method",
        "observed_at",
        "source_system",
        "contract_version",
    ):
        req = _kw(fields[name], "required")
        assert isinstance(req, ast.Constant) and req.value is True, name
    for name, ondelete in [
        ("company_id", "restrict"),
        ("material_profile_id", "cascade"),
        ("specification_id", "set null"),
        ("supersedes_id", "restrict"),
    ]:
        od = _kw(fields[name], "ondelete")
        assert isinstance(od, ast.Constant) and od.value == ondelete, (name, ondelete)
    assert _call_name(fields["value_json"]) == "Json"


def test_acl_and_chatter_wiring() -> None:
    rows = list(csv.DictReader((MOD / "security" / "ir.model.access.csv").open()))
    models = {r["model_id:id"] for r in rows}
    assert "model_plasticos_material_specification" in models
    assert "model_plasticos_material_observation" in models
    assert "<chatter/>" in (MOD / "views" / "material_specification_views.xml").read_text()
    assert "<chatter/>" not in (MOD / "views" / "material_observation_views.xml").read_text()


def test_no_scoring_or_gate_in_models() -> None:
    forbidden = ("score(", "ranking", "send_to_gate", "TransportPacket", "match_engine")
    for path in (MOD / "models").glob("*.py"):
        text = path.read_text()
        for token in forbidden:
            assert token not in text, f"{path.name} contains {token}"
