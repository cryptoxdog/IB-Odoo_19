"""Filler and process survive the phrase table.

The matrix columns are not a second runtime table. A phrase carries them only
when its ``_SPECS`` entry names them, and HDPE Crates is the first phrase that
names the injection process.
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
        "material_normalizer_process_filler",
        PROFILE / "models" / "material_normalizer.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hdpe_crates_spec_names_injection_and_the_matrix_matches():
    normalizer = _load_normalizer()
    spec = normalizer._SPECS["hdpe crates"]
    assert spec == normalizer._spec(
        polymer="HDPE",
        material_grade="CRATES",
        packaging_type="loose",
        process_type="injection",
    )
    assert spec.filler_type is None
    with MATRIX.open(encoding="utf-8", newline="") as handle:
        row = next(row for row in csv.DictReader(handle) if row["match_key"] == "hdpe crates")
    assert row["process_type"] == "injection"
    assert row["filler_type"] == ""
    assert row["material_grade"] == "CRATES"
    assert row["packaging_type"] == "loose"
    assert len(row) == 20
