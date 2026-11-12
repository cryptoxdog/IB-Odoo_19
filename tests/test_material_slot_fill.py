"""Corrected matrix rows match the worksheet phrase table.

Form BALES is packaging. A phrase that says shrink takes grade SHRINK_WRAP.
Stretch film does not. Each new worksheet phrase matches its matrix row.
A call note or a not-material row is skipped by the CRM importer, never
reported as an unresolved material.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
import types
from pathlib import Path

import pytest

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
    assert "shrink wrap" not in _load_normalizer().phrase_table()


def test_changed_specs_match_the_matrix_and_the_drum_regrind_stores_both_colors():
    normalizer = _load_normalizer()
    phrases = normalizer.phrase_table()
    rows = {row["match_key"]: row for row in _rows()}
    drum = phrases["hdpe blue/white drum regrind"]
    assert drum.polymer == "HDPE"
    assert drum.material_grade == "DRUMS"
    assert drum.form == "REGRIND"
    assert drum.color == ("BLUE", "WHITE")
    skipped = phrases["hmw dunnage trays"]
    assert skipped.polymer == "HDPE_HMW"
    assert skipped.material_grade is None
    blends = (
        "ldpe/mdpe film rolls and post industrial bales",
        "ldpe / mdpe mixed color film",
        "ldpe/mdpe printed rolls",
        "rejected material - pet clear sheet w/ petg contamination",
    )
    for key in blends:
        assert rows[key]["status"] == "ambiguous"
        assert "two polymers" in rows[key]["note"]
        assert key not in phrases
    for key, spec in phrases.items():
        row = rows[key]
        assert row["status"] == "mapped"
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


def test_every_non_material_row_is_recognised_and_never_a_phrase():
    normalizer = _load_normalizer()
    phrases = normalizer.phrase_table()
    rows = _rows()
    skipped = [row for row in rows if row["status"] in ("not_material", "note_not_material")]
    assert {row["status"] for row in skipped} == {"not_material", "note_not_material"}
    for row in skipped:
        assert row["match_key"] not in phrases
        assert normalizer.is_not_material(row["source_value"])
        assert normalizer.is_not_material(f"  {row['match_key'].upper()}  ")
    for row in rows:
        if row["status"] in ("mapped", "ambiguous", "unknown"):
            assert not normalizer.is_not_material(row["match_key"])
    assert not normalizer.is_not_material("")


@pytest.fixture
def store_orchestrator(monkeypatch):
    """The real ``_store_normalized_materials`` with the Odoo seams replaced."""
    root = str(ROOT)
    if root not in sys.path:
        monkeypatch.syspath_prepend(root)
    from plasticos_crm_sync.services import orchestrator as orchestrator_module  # noqa: PLC0415

    normalizer = _load_normalizer()
    exceptions = types.ModuleType("odoo.exceptions")
    exceptions.ValidationError = type("ValidationError", (Exception,), {})
    for name, module in (
        ("odoo", types.ModuleType("odoo")),
        ("odoo.exceptions", exceptions),
        ("odoo.addons", types.ModuleType("odoo.addons")),
        ("odoo.addons.plasticos_material_profile", types.ModuleType("odoo.addons.plasticos_material_profile")),
        (
            "odoo.addons.plasticos_material_profile.models",
            types.ModuleType("odoo.addons.plasticos_material_profile.models"),
        ),
        ("odoo.addons.plasticos_material_profile.models.material_normalizer", normalizer),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    class _Unresolved:
        unresolved = ("unresolved material",)
        polymer = None

        def __init__(self, text):
            self.source_description = text

    orchestrator = orchestrator_module.SyncOrchestrator.__new__(orchestrator_module.SyncOrchestrator)
    orchestrator.env = {"plasticos.material.profile": object()}
    orchestrator.resolved = []
    orchestrator.errors = []
    orchestrator._material_ref = lambda lead, external_id: external_id
    orchestrator._resolve_material = lambda text, structured=None: (
        orchestrator.resolved.append(text) or (_Unresolved(text), None)
    )
    orchestrator._append_classified_error = lambda ref, message, category: orchestrator.errors.append(
        (ref, message, category)
    )
    return orchestrator, orchestrator_module


def test_crm_import_skips_call_notes_and_not_material_text(store_orchestrator):
    orchestrator, _module = store_orchestrator
    skipped = [row["source_value"] for row in _rows() if row["status"] in ("not_material", "note_not_material")]
    orchestrator._store_normalized_materials(None, skipped, partner=object(), external_id="VS-1")
    assert orchestrator.resolved == []
    assert orchestrator.errors == []


def test_crm_import_still_reports_an_unmapped_material(store_orchestrator):
    orchestrator, module = store_orchestrator
    orchestrator._store_normalized_materials(None, ["zz unmapped phrase"], partner=object(), external_id="VS-2")
    assert orchestrator.resolved == ["zz unmapped phrase"]
    assert orchestrator.errors == [("VS-2", "unresolved material: zz unmapped phrase", module.REQUIRED_MAPPING)]
