"""Repo-level TASK-023: plasticos_semantic_kernel specification/observation models."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plasticos_semantic_kernel"

FORBIDDEN_IMPORT = re.compile(
    r"^\s*(from|import)\s+(neo4j|requests|httpx|constellation_node_sdk|gate_client)",
    re.M,
)


def test_module_layout() -> None:
    assert (MOD / "__manifest__.py").is_file()
    assert (MOD / "__init__.py").is_file()
    assert (MOD / "models" / "material_specification.py").is_file()
    assert (MOD / "models" / "material_observation.py").is_file()
    assert (MOD / "security" / "ir.model.access.csv").is_file()
    assert (MOD / "views" / "menus.xml").is_file()


def test_manifest_contract() -> None:
    manifest = ast.literal_eval((MOD / "__manifest__.py").read_text())
    assert manifest["name"] == "PlasticOS Semantic Kernel"
    assert manifest["version"].startswith("19.0.")
    assert manifest["installable"] is True
    depends = set(manifest["depends"])
    assert {"mail", "plasticos_material_profile", "plasticos_facility_profile", "plasticos_intake"} <= depends
    assert "plasticos_gate" not in depends
    assert "security/ir.model.access.csv" in manifest["data"]
    assert "views/material_specification_views.xml" in manifest["data"]


def test_no_intelligence_or_gate_code() -> None:
    for path in MOD.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        text = path.read_text()
        assert not FORBIDDEN_IMPORT.search(text), f"forbidden import in {path}"
        assert "send_to_gate" not in text
        assert "TransportPacket" not in text


def test_acl_has_model_rows() -> None:
    rows = (MOD / "security" / "ir.model.access.csv").read_text().strip().splitlines()
    assert rows[0].startswith("id,name,model_id:id")
    assert len(rows) > 1
    body = "\n".join(rows[1:])
    assert "model_plasticos_material_specification" in body
    assert "model_plasticos_material_observation" in body
