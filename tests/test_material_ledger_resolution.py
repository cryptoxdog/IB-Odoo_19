"""The closed ledger is gone and its 19 phrases are mapped.

``material_mapping.csv`` holds the cells. The remaining file is not a second list.
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "plasticos_material_profile" / "data"
LEDGER = DATA / "material_mapping_resolution_ledger_11-04-26.csv"
REMAINING = DATA / "material_mapping_resolution_remaining.csv"
MATRIX = DATA / "material_mapping.csv"

APPROVED = {
    "z bales": ("HDPE", "BOTTLES", "", "MIXED", "POST_CONSUMER", "", "", "bales"),
    "z-bales": ("HDPE", "BOTTLES", "", "MIXED", "POST_CONSUMER", "", "", "bales"),
    "1 & 2 bottles": ("1_2_COMMINGLED_BOTTLES", "BOTTLES", "", "", "POST_CONSUMER", "", "", "bales"),
    "bottles (hd/pet)": ("1_2_COMMINGLED_BOTTLES", "BOTTLES", "", "", "POST_CONSUMER", "", "", "bales"),
    "1 & 2 bottles (pet/hdpe)": ("1_2_COMMINGLED_BOTTLES", "BOTTLES", "", "", "POST_CONSUMER", "", "", "bales"),
    "1 & 2 pet & hdpe co-mingled bottles (post consumer)": (
        "1_2_COMMINGLED_BOTTLES",
        "BOTTLES",
        "",
        "",
        "POST_CONSUMER",
        "",
        "",
        "bales",
    ),
    "commingled bottles 1&2": ("1_2_COMMINGLED_BOTTLES", "BOTTLES", "", "", "POST_CONSUMER", "", "", "bales"),
    "ldpe/hdpe grocery film": ("MIXED", "", "FILM", "", "", "", "", ""),
    "mixed hd/pp pallets and knockdowns": ("PP_PE", "PALLETS", "", "", "", "", "", ""),
    "pe / pp regrind mixed": ("PP_PE", "", "REGRIND", "", "", "", "mixed", ""),
    "hdpe / ldpe regrind": ("MIXED", "", "REGRIND", "", "", "", "", ""),
    "compression molded regrind": ("PLASTIC_PALLETS", "", "REGRIND", "", "", "compression_mold", "", ""),
    "hd and pp purge/regrind/fluff": ("PP_PE", "", "", "", "", "", "mixed", ""),
    "compression molded": ("PLASTIC_PALLETS", "PALLETS", "", "", "", "compression_mold", "", ""),
    "mixed dunnage trays": ("PLASTIC_PALLETS", "DUNNAGE", "", "", "", "", "", ""),
    "red totes on casters": ("HDPE", "TOTERS", "", "RED", "", "", "", ""),
    "plastic totes / trash cans (empty and clean)": ("HDPE", "TOTES", "", "", "", "", "clean", ""),
    "gaylords of amazon returns": ("MIXED", "RETURNS", "", "", "", "", "", "gaylords"),
    "mixed plastic pallets - pp skids": ("PP", "PALLETS", "", "", "", "", "", ""),
}


def _rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_the_nineteen_phrases_are_mapped_and_the_ledger_files_are_gone():
    assert not LEDGER.exists()
    assert not REMAINING.exists()
    matrix = {row["match_key"]: row for row in _rows(MATRIX)}
    for key, expected in APPROVED.items():
        row = matrix[key]
        actual = (
            row["polymer"],
            row["material_grade"],
            row["form"],
            row["color"],
            row["source_type"],
            row["process_type"],
            row["attributes"],
            row["packaging_type"],
        )
        assert actual == expected, (key, actual)
        assert row["status"] == "mapped"
