"""Recurrence guard: no mapping file or code table maps a bale word to a form.

Bales are packaging (``plasticos.packaging.type`` code ``bales``), never a form
(operator decision; PR #516 / #517). This fails when any source of truth for an
import, a sync or the web-lead/enrichment vocabularies sends bale, bales or baled
to a form again. Frozen evidence (``docs/``, the ERP bulk extract) is not checked.
"""

from __future__ import annotations

import ast
import csv
import importlib.util
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
BALE = re.compile(r"\bbal(e|es|ed)\b", re.IGNORECASE)
MAPPING_FILES = (
    PROFILE / "data" / "material_mapping.csv",
    PROFILE / "data" / "ERP-Products.csv",
    ROOT / "plasticos_crm_sync" / "data" / "vanillasoft_material_mapping.csv",
)
BALE_WORDS = ("bale", "bales", "baled")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _inactive(path: Path, record_id: str) -> bool:
    for record in ET.parse(path).getroot().iter("record"):  # noqa: S314 - repository seed file
        if record.get("id") == record_id:
            active = record.find("field[@name='active']")
            return active is not None and (active.get("eval") or "").casefold() == "false"
    raise AssertionError(f"{record_id} is missing from {path}")


def _dict_literal(path: Path, name: str) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is missing from {path}")


@pytest.mark.parametrize("path", MAPPING_FILES, ids=lambda p: p.name)
def test_no_mapping_row_sends_a_bale_value_to_a_form(path: Path) -> None:
    offenders = []
    for line, row in enumerate(_rows(path), start=2):
        form = row.get("form") or ""
        if BALE.search(form):
            offenders.append(f"{path.name}:{line} form={form}")
    assert offenders == []


def test_bale_hint_rows_map_to_packaging_bales() -> None:
    rows = {row["match_key"]: row for row in _rows(PROFILE / "data" / "material_mapping.csv")}
    for word in ("bales", "baled"):
        row = rows[word]
        assert row["form"] == "", word
        assert row["packaging_type"] == "bales", word


def test_form_codes_hold_no_bale_code() -> None:
    forms = _load(PROFILE / "form_codes.py", "_bales_form_codes")
    assert [code for code in forms.FORM_CODES if BALE.search(code)] == []
    assert [code for code in forms.EQUIPMENT_GATED_FORMS if BALE.search(code)] == []
    assert [code for code, _label in forms.FORM_SELECTION if BALE.search(code)] == []


def test_normalizer_form_words_hold_no_bale_word() -> None:
    normalizer = _load(PROFILE / "models" / "material_normalizer.py", "_bales_normalizer")
    words = normalizer.form_words()
    assert [word for word in words if BALE.search(word)] == []
    assert [code for code in words.values() if BALE.search(code)] == []


def test_enrichment_maps_bale_words_to_packaging_only() -> None:
    service = ROOT / "plasticos_enrichment" / "models" / "enrichment_service.py"
    form_normalize = _dict_literal(service, "FORM_NORMALIZE")
    form_master = _dict_literal(service, "FORM_CODE_TO_MASTER")
    assert [key for key, value in form_normalize.items() if BALE.search(key) or BALE.search(str(value))] == []
    assert [key for key, value in form_master.items() if BALE.search(key) or BALE.search(str(value))] == []
    assert {word: _dict_literal(service, "PACKAGING_NORMALIZE").get(word) for word in BALE_WORDS} == dict.fromkeys(
        BALE_WORDS, "bales"
    )


def test_matrix_generator_sends_bale_words_to_packaging() -> None:
    script = ROOT / "scripts" / "build_material_mapping.py"
    decisions = _dict_literal(script, "HINT_DECISIONS")
    for word in BALE_WORDS:
        assert decisions[word] == ("packaging_type", "bales"), word
    assert [word for word in _dict_literal(script, "FORM_WORDS").get("BALES", ())] == []


def test_bale_form_records_are_archived() -> None:
    assert _inactive(PROFILE / "data" / "material_form_data.xml", "form_bale")
    assert _inactive(ROOT / "plasticos_base" / "data" / "material_taxonomy.xml", "form_bale")
