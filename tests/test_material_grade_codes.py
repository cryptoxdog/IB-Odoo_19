"""Material grade codes match their seed, and no former form code is still a form.

``plasticos_material_profile/grade_codes.py`` is the grade code registry and
``form_codes.py`` the form code registry. Drums, Buckets, Bottles, Pallets, Crates and
Totes moved from forms to grades in 19.0.5.11.0; a form record or form code with one of
those codes would split the same material across two masters. Pure: reads the module's
Python registries and seed XML only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from defusedxml import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"plasticos_{name}", PROFILE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed(filename: str, model: str) -> dict[str, dict[str, str]]:
    records = {}
    for record in ElementTree.parse(PROFILE / "data" / filename).iter("record"):
        if record.get("model") != model:
            continue
        values = {field.get("name"): (field.text or "").strip() for field in record.findall("field")}
        active = record.find("field[@name='active']")
        values["active"] = not (active is not None and (active.get("eval") or "").casefold() == "false")
        records[record.get("id")] = values
    return records


GRADES = _load("grade_codes")
FORMS = _load("form_codes")


def test_grade_codes_equal_the_grade_seed_in_order() -> None:
    seed = _seed("material_grade_data.xml", "plasticos.material.grade")
    assert [values["code"] for values in seed.values()] == list(GRADES.GRADE_CODES)


def test_grade_xmlids_carry_the_material_grade_prefix() -> None:
    seed = _seed("material_grade_data.xml", "plasticos.material.grade")
    assert sorted(seed) == sorted(f"material_grade_{code.lower()}" for code in GRADES.GRADE_CODES)


def test_displayed_names_are_title_case_except_acronyms() -> None:
    names = {
        values["code"]: values["name"]
        for values in _seed("material_grade_data.xml", "plasticos.material.grade").values()
    }
    assert names["OCC"] == "OCC"
    assert names["IBC_TOTES"] == "IBC Totes"
    assert names["TUBS_LIDS"] == "Tubs/Lids"
    assert names["RETURNS"] == "Returns"
    assert names["SHRINK_WRAP"] == "Shrink Wrap"
    assert len(names) == 35


def test_form_codes_equal_the_form_seed() -> None:
    # Active forms only: the archived Bales form (packaging, not a form) is not a form code.
    seed = _seed("material_form_data.xml", "plasticos.material.form")
    assert sorted(values["code"] for values in seed.values() if values["active"]) == sorted(FORMS.FORM_CODES)
    assert [values["code"] for values in seed.values() if not values["active"]] == ["BALES"]


def test_former_form_codes_are_grades_and_no_longer_forms() -> None:
    form_seed = {values["code"] for values in _seed("material_form_data.xml", "plasticos.material.form").values()}
    for code in GRADES.FORMER_FORM_CODES:
        assert code in GRADES.GRADE_CODES
        assert code not in FORMS.FORM_CODES
        assert code not in form_seed


def test_grade_templates_reference_seeded_grades_only() -> None:
    grade_ids = set(_seed("material_grade_data.xml", "plasticos.material.grade"))
    for record in ElementTree.parse(PROFILE / "data" / "grade_template_data.xml").iter("record"):
        for field in record.findall("field"):
            if field.get("name") == "material_grade_id":
                assert field.get("ref") in grade_ids, record.get("id")
            if field.get("name") == "form_id":
                assert field.get("ref") not in {f"form_{code.lower()}" for code in GRADES.FORMER_FORM_CODES}
