"""Repo-level TASK-022: plasticos_semantic_kernel is an install-only skeleton."""

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
    assert (MOD / "models" / "__init__.py").is_file()
    assert (MOD / "security" / "ir.model.access.csv").is_file()


def test_manifest_contract() -> None:
    manifest = ast.literal_eval((MOD / "__manifest__.py").read_text())
    assert manifest["name"] == "PlasticOS Semantic Kernel"
    assert manifest["version"].startswith("19.0.")
    assert manifest["installable"] is True
    assert set(manifest["depends"]) == {
        "plasticos_material_profile",
        "plasticos_facility_profile",
        "plasticos_intake",
    }
    # Zero behavior: no services/clients in this slice
    assert "data" in manifest
    assert manifest["data"] == ["security/ir.model.access.csv"]


def test_no_intelligence_or_gate_code() -> None:
    for path in MOD.rglob("*.py"):
        text = path.read_text()
        assert not FORBIDDEN_IMPORT.search(text), f"forbidden import in {path}"
        assert "send_to_gate" not in text
        assert "TransportPacket" not in text
        assert "match(" not in text or path.name.startswith("test_")


def test_acl_header_only_until_models() -> None:
    rows = (MOD / "security" / "ir.model.access.csv").read_text().strip().splitlines()
    assert rows[0].startswith("id,name,model_id:id")
    assert len(rows) == 1
