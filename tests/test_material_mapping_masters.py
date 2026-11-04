"""Every mapped row in the material matrix names masters that are seeded.

``plasticos_material_profile/data/material_mapping.csv`` is the importers' lookup. A
mapped row whose polymer, form or other code has no seeded master record resolves to
``missing <model> <code>`` at runtime, so the row silently stops mapping. This guard
reads the committed matrix and the module's seed XML only; it needs no Odoo runtime.

Found 2026-11-04 (four-PR integration review): 25 mapped rows named nine polymers
(TPU, TPV, PVB, PU_FOAM, TEXTILE, UBC, FIBERGLASS, WOOD_PALLETS, AUTO_PARTS) that the
builder supplied from a fallback set and polymer_data.xml did not seed.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
from pathlib import Path

import pytest
from defusedxml import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
MATRIX = PROFILE / "data" / "material_mapping.csv"

# Matrix column -> seed file whose records' ``code`` field it must name.
MASTER_FILES = {
    "polymer": "polymer_data.xml",
    "material_grade": "material_grade_data.xml",
    "form": "material_form_data.xml",
    "source_type": "source_type_data.xml",
    "attributes": "material_attribute_data.xml",
    "color": "material_color_data.xml",
    "filler_type": "filler_type_data.xml",
    "packaging_type": "packaging_type_data.xml",
    "grade_template": "grade_template_data.xml",
}


def _codes(filename: str) -> set[str]:
    tree = ElementTree.parse(PROFILE / "data" / filename)
    found = set()
    for record in tree.iter("record"):
        for field in record.findall("field"):
            if field.get("name") == "code" and (field.text or "").strip():
                found.add(" ".join(field.text.split()))
    return found


def _process_codes() -> set[str]:
    spec = importlib.util.spec_from_file_location("plasticos_process_codes", PROFILE / "process_codes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module.PROCESS_CODES)


def _mapped_rows() -> list[dict[str, str]]:
    with MATRIX.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["status"] == "mapped"]


def _polymer_selection_codes() -> set[str]:
    """Keys of the stored ``polymer`` Selection on plasticos.material.profile."""
    tree = ast.parse((PROFILE / "models" / "material_profile.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "polymer" for t in node.targets)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "attr", "") == "Selection"
        ):
            choices = node.value.args[0]
            assert isinstance(choices, ast.List)
            return {ast.literal_eval(item)[0] for item in choices.elts}
    raise AssertionError("polymer Selection not found in material_profile.py")


def test_the_matrix_has_mapped_rows() -> None:
    assert len(_mapped_rows()) > 100


@pytest.mark.parametrize("column", sorted(MASTER_FILES))
def test_every_mapped_code_has_a_seeded_master(column: str) -> None:
    seeded = _codes(MASTER_FILES[column])
    assert seeded, f"{MASTER_FILES[column]} seeds no codes"
    missing: dict[str, int] = {}
    for row in _mapped_rows():
        values = row[column].split() if column == "attributes" else [row[column].strip()]
        for value in values:
            if value and value not in seeded:
                missing[value] = missing.get(value, 0) + 1
    assert not missing, f"mapped {column} codes with no master in {MASTER_FILES[column]}: {missing}"


def test_every_mapped_process_is_a_known_process_code() -> None:
    known = _process_codes()
    missing = {
        row["process_type"] for row in _mapped_rows() if row["process_type"] and row["process_type"] not in known
    }
    assert not missing, missing


def test_every_mapped_polymer_projects_onto_the_stored_code() -> None:
    """_compute_polymer_code writes False for a code outside the Selection."""
    selection = _polymer_selection_codes()
    missing = {row["polymer"] for row in _mapped_rows() if row["polymer"] and row["polymer"] not in selection}
    assert not missing, f"mapped polymers outside the material_profile polymer Selection: {sorted(missing)}"
