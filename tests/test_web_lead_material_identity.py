"""Web-lead material identity: one code splits to a form or a grade, and HOT/COLD does not move.

Pure: loads the grade and form registries, the split helper, the economic policy, and the
broker snapshot builder by file path. ``_FORM_NORMALIZE`` is read from ``web_lead.py``
source because that module imports Odoo.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"
WEB_LEADS_MODELS = ROOT / "plasticos_web_leads" / "models"
_PACKAGE = "_web_lead_identity_models"

if _PACKAGE not in sys.modules:
    sys.modules[_PACKAGE] = types.ModuleType(_PACKAGE)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


GRADES = _load(PROFILE / "grade_codes.py", "_web_lead_identity_grade_codes")
FORMS = _load(PROFILE / "form_codes.py", "_web_lead_identity_form_codes")
IDENTITY = _load(WEB_LEADS_MODELS / "material_identity.py", f"{_PACKAGE}.material_identity")
POLICY = _load(WEB_LEADS_MODELS / "economic_policy.py", f"{_PACKAGE}.economic_policy")
KEYS = _load(WEB_LEADS_MODELS / "evidence_keys.py", f"{_PACKAGE}.evidence_keys")
SNAPSHOT = _load(WEB_LEADS_MODELS / "review_snapshot.py", f"{_PACKAGE}.review_snapshot")

split_material_code = IDENTITY.split_material_code
merge_form_and_grade = IDENTITY.merge_form_and_grade
GRADE_CODES = GRADES.GRADE_CODES
FORM_CODES = FORMS.FORM_CODES


def _form_normalize_values() -> list[str]:
    tree = ast.parse((WEB_LEADS_MODELS / "web_lead.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "_FORM_NORMALIZE":
            assert isinstance(node.value, ast.Dict)
            return [value.value for value in node.value.values if isinstance(value, ast.Constant)]
    raise AssertionError("_FORM_NORMALIZE not found in web_lead.py")


FORM_NORMALIZE_VALUES = sorted(set(_form_normalize_values()))


def _eligibility(lbs: float, *, polymer=None, form=None, grade=None):
    return POLICY.evaluate_economic_eligibility(
        estimated_lbs=lbs,
        standard_hot_min_lbs=10_000.0,
        reusable_item_hot_min_lbs=8_000.0,
        polymer_code=polymer,
        form_code=form,
        material_grade_code=grade,
        reusable_item_policy_codes=POLICY.DEFAULT_REUSABLE_ITEM_POLICY_CODES,
    )


def test_grade_and_form_registries_are_disjoint() -> None:
    assert not set(GRADE_CODES) & set(FORM_CODES)


def test_every_web_lead_material_code_is_a_form_or_a_grade() -> None:
    known = set(GRADE_CODES) | set(FORM_CODES)
    assert [code for code in FORM_NORMALIZE_VALUES if code not in known] == []


@pytest.mark.parametrize("code", GRADE_CODES)
def test_grade_codes_split_to_a_grade_with_no_form(code: str) -> None:
    assert split_material_code(code, GRADE_CODES) == (None, code)


@pytest.mark.parametrize("code", ["SHEET", "FILM", "REGRIND", "FLUFF", "OTHER"])
def test_form_codes_split_to_a_form_with_no_grade(code: str) -> None:
    assert split_material_code(code, GRADE_CODES) == (code, None)


def test_split_upper_cases_and_treats_empty_as_unknown() -> None:
    assert split_material_code(" pallets ", GRADE_CODES) == (None, "PALLETS")
    assert split_material_code(None, GRADE_CODES) == (None, None)
    assert split_material_code("  ", GRADE_CODES) == (None, None)


def test_item_grade_keeps_a_vision_physical_form() -> None:
    assert merge_form_and_grade(None, "HDPE drums", "REGRIND", GRADE_CODES) == ("REGRIND", "DRUMS")


def test_ai_physical_form_still_collects_the_item_grade() -> None:
    assert merge_form_and_grade("FILM", "plastic buckets", None, GRADE_CODES) == ("FILM", "BUCKETS")


def test_ai_grade_does_not_block_a_vision_form() -> None:
    assert merge_form_and_grade("DRUMS", "drums", "REGRIND", GRADE_CODES) == ("REGRIND", "DRUMS")


def test_pallet_text_alone_is_a_grade_with_no_form() -> None:
    assert merge_form_and_grade(None, "HDPE plastic pallets", None, GRADE_CODES) == (None, "PALLETS")


def test_film_alone_stays_a_form() -> None:
    assert merge_form_and_grade("FILM", "LDPE scrap", None, GRADE_CODES) == ("FILM", None)


def test_pallet_beats_tote_when_both_are_named() -> None:
    assert merge_form_and_grade(None, "pallets and totes", None, GRADE_CODES)[1] == "PALLETS"


def test_vision_does_not_replace_an_ai_physical_form() -> None:
    assert merge_form_and_grade("FILM", "LDPE scrap", "REGRIND", GRADE_CODES) == ("FILM", None)


def test_text_grade_wins_over_a_vision_grade() -> None:
    assert merge_form_and_grade(None, "plastic pallets", "DRUMS", GRADE_CODES) == (None, "PALLETS")


def test_web_lead_merge_collects_grade_separately_from_form() -> None:
    source = (WEB_LEADS_MODELS / "web_lead.py").read_text(encoding="utf-8")
    assert "merge_form_and_grade(" in source
    assert 'merged["form"] = form_code' not in source


@pytest.mark.parametrize("lbs", [7_900.0, 8_500.0, 10_500.0])
@pytest.mark.parametrize("code", [*FORM_NORMALIZE_VALUES, None])
def test_split_keeps_every_hot_cold_decision(code, lbs: float) -> None:
    form, grade = split_material_code(code, GRADE_CODES)
    before = _eligibility(lbs, polymer="HDPE", form=code)
    after = _eligibility(lbs, polymer="HDPE", form=form, grade=grade)
    assert after.to_dict() == before.to_dict()


@pytest.mark.parametrize("form", ["ROLLSTOCK", "FILM"])
def test_film_and_rollstock_both_use_the_standard_threshold(form: str) -> None:
    result = _eligibility(8_500.0, polymer="LDPE", form=form)
    assert result.applicable_hot_min_lbs == 10_000.0
    assert result.eligible is False


@pytest.mark.parametrize("grade", ["PALLETS", "TOTES", "CRATES"])
def test_reusable_item_grade_with_no_form_is_hot_at_the_lower_threshold(grade: str) -> None:
    result = _eligibility(8_500.0, grade=grade)
    assert result.eligible is True
    assert result.policy_applied == "reusable_item"
    assert result.applicable_hot_min_lbs == 8_000.0


def test_no_form_and_no_grade_keeps_the_standard_threshold() -> None:
    assert _eligibility(8_500.0).eligible is False


@pytest.mark.parametrize("grade", ["DRUMS", "BUCKETS", "BOTTLES"])
def test_other_grades_keep_the_standard_threshold(grade: str) -> None:
    result = _eligibility(8_500.0, polymer="HDPE", grade=grade)
    assert result.applicable_hot_min_lbs == 10_000.0
    assert result.eligible is False


def test_broker_snapshot_carries_the_intake_material_grade() -> None:
    def master(record_id: int, code: str):
        return SimpleNamespace(id=record_id, code=code)

    lead = SimpleNamespace(
        lead_id="WL-1",
        provider_key="typeform",
        provider_external_id="ext-1",
        canonical_payload={"material_description": "HDPE drums"},
        evidence_bundle={},
        decision_reasons={"reasons": []},
    )
    intake = SimpleNamespace(
        id=7,
        name="INT-7",
        polymer_id=master(1, "HDPE"),
        form_id=master(2, "OTHER"),
        material_grade_id=master(3, "DRUMS"),
        source_type_id=None,
        quantity_per_load_lbs=12_000,
        loads_per_month=1,
        pending_company_name="Seller",
        partner_id=None,
        facility_id=None,
    )

    payload = SNAPSHOT.build_snapshot_payload(lead=lead, intake=intake, review_notes=None)

    block = payload[KEYS.KEY_INTAKE]
    assert block[KEYS.KEY_FORM_CODE] == "OTHER"
    assert block[KEYS.KEY_MATERIAL_GRADE_ID] == 3
    assert block[KEYS.KEY_MATERIAL_GRADE_CODE] == "DRUMS"
