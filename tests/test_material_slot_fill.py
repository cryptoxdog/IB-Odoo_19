"""Corrected matrix rows match the worksheet phrase table.

Form BALES is packaging. A phrase that says shrink takes grade SHRINK_WRAP.
Stretch film does not. Each new worksheet phrase matches its matrix row.
"""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
MATRIX = PROFILE / "data" / "material_mapping.csv"


def _load_normalizer():
    spec = importlib.util.spec_from_file_location(
        "material_normalizer_slot_fill",
        PROFILE / "models" / "material_normalizer.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows():
    with MATRIX.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row["field_role"] == "material"]


def test_no_mapped_row_uses_form_bales():
    assert not [row["match_key"] for row in _rows() if row["status"] == "mapped" and row["form"] == "BALES"]


def test_shrink_phrases_take_shrink_wrap_and_stretch_film_stays():
    rows = {row["match_key"]: row for row in _rows()}
    assert rows["ldpe stretch film"]["material_grade"] == "STRETCH_FILM"
    shrink = [row for row in rows.values() if "shrink" in row["match_key"]]
    assert shrink
    assert {row["material_grade"] for row in shrink} == {"SHRINK_WRAP"}
    assert "shrink wrap" not in _load_normalizer()._SPECS


def test_changed_specs_match_the_matrix_and_the_drum_regrind_stores_both_colors():
    normalizer = _load_normalizer()
    rows = {row["match_key"]: row for row in _rows()}
    drum = normalizer._SPECS["hdpe blue/white drum regrind"]
    assert drum.polymer == "HDPE"
    assert drum.material_grade == "DRUMS"
    assert drum.form == "REGRIND"
    assert drum.color == ("BLUE", "WHITE")
    skipped = normalizer._SPECS["hmw dunnage trays"]
    assert skipped.polymer == "HDPE_HMW"
    assert skipped.material_grade is None
    for key, spec in normalizer._SPECS.items():
        row = rows[key]
        assert spec.polymer == row["polymer"]
        assert (spec.material_grade or "") == row["material_grade"]
        assert (spec.form or "") == row["form"]
        assert (spec.source or "") == row["source_type"]
        assert " ".join(spec.attributes) == row["attributes"]
        assert " ".join(spec.color) == row["color"]
        assert (spec.packaging_type or "") == row["packaging_type"]
        assert (spec.process_type or "") == row["process_type"]
        assert (spec.filler_type or "") == row["filler_type"]
        assert (spec.grade or "") == row["grade"]
