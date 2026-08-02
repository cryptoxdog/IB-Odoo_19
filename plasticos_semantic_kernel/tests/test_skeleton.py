"""In-module skeleton checks for plasticos_semantic_kernel (TASK-022)."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_depends_and_installable() -> None:
    manifest = ast.literal_eval((ROOT / "__manifest__.py").read_text())
    assert manifest["installable"] is True
    assert manifest["application"] is False
    assert set(manifest["depends"]) == {
        "plasticos_material_profile",
        "plasticos_facility_profile",
        "plasticos_intake",
    }
    assert "plasticos_gate" not in manifest["depends"]
    assert "external_dependencies" not in manifest


def test_no_models_yet() -> None:
    models_dir = ROOT / "models"
    py_files = [p for p in models_dir.glob("*.py") if p.name != "__init__.py"]
    assert py_files == [], f"skeleton must not define models yet: {py_files}"
