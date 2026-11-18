"""Web-lead material identity: one code splits to a form or a grade, and HOT/COLD does not move.

Pure: loads the grade and form registries, the catalog matcher, the economic policy, and the
broker snapshot builder by file path.
"""

from __future__ import annotations

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
CATALOG = _load(WEB_LEADS_MODELS / "material_catalog.py", f"{_PACKAGE}.material_catalog")
IDENTITY = _load(WEB_LEADS_MODELS / "material_identity.py", f"{_PACKAGE}.material_identity")
POLICY = _load(WEB_LEADS_MODELS / "economic_policy.py", f"{_PACKAGE}.economic_policy")
KEYS = _load(WEB_LEADS_MODELS / "evidence_keys.py", f"{_PACKAGE}.evidence_keys")
SNAPSHOT = _load(WEB_LEADS_MODELS / "review_snapshot.py", f"{_PACKAGE}.review_snapshot")

split_material_code = IDENTITY.split_material_code
merge_form_and_grade = IDENTITY.merge_form_and_grade
GRADE_CODES = GRADES.GRADE_CODES
FORM_CODES = FORMS.FORM_CODES
MATERIAL_CODES = sorted(set(FORM_CODES) | set(GRADE_CODES))


def _entries(codes):
    return tuple(CATALOG.CatalogEntry(code, code.replace("_", " ").title(), "") for code in codes)


FORM_ENTRIES = _entries(FORM_CODES)
GRADE_ENTRIES = _entries(GRADE_CODES)
NORMALIZER = _load(PROFILE / "models" / "material_normalizer.py", "_web_lead_identity_normalizer")
FORM_WORD_CODES = sorted(set(NORMALIZER.form_words().values()))
GRADE_WORD_CODES = sorted(set(NORMALIZER.grade_words().values()))


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


def test_normalizer_word_tables_keep_forms_and_grades_apart() -> None:
    assert [code for code in FORM_WORD_CODES if code not in FORM_CODES] == []
    assert [code for code in GRADE_WORD_CODES if code not in GRADE_CODES] == []
    assert not set(NORMALIZER.form_words()) & set(NORMALIZER.grade_words())


def test_catalog_accepts_a_listed_code_and_drops_any_other() -> None:
    assert CATALOG.accept_value("FILM", FORM_ENTRIES) == "FILM"
    assert CATALOG.accept_value("film", FORM_ENTRIES) == "FILM"
    assert CATALOG.accept_value("not-a-form", FORM_ENTRIES) is None
    assert CATALOG.accept_value("PALLETS", GRADE_ENTRIES) == "PALLETS"
    assert CATALOG.accept_value("rpet", _entries(("HDPE", "PP", "PET"))) is None


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
    assert merge_form_and_grade(None, "HDPE drums", "REGRIND", FORM_ENTRIES, GRADE_ENTRIES) == ("REGRIND", "DRUMS")


def test_ai_physical_form_still_collects_the_item_grade() -> None:
    assert merge_form_and_grade("FILM", "plastic buckets", None, FORM_ENTRIES, GRADE_ENTRIES) == ("FILM", "BUCKETS")


def test_ai_grade_does_not_block_a_vision_form() -> None:
    assert merge_form_and_grade("DRUMS", "drums", "REGRIND", FORM_ENTRIES, GRADE_ENTRIES) == ("REGRIND", "DRUMS")


def test_pallet_text_alone_is_a_grade_with_no_form() -> None:
    assert merge_form_and_grade(None, "HDPE plastic pallets", None, FORM_ENTRIES, GRADE_ENTRIES) == (None, "PALLETS")


def test_film_alone_stays_a_form() -> None:
    assert merge_form_and_grade("FILM", "LDPE scrap", None, FORM_ENTRIES, GRADE_ENTRIES) == ("FILM", None)


def test_stretch_film_fills_grade_and_form() -> None:
    forms = (CATALOG.CatalogEntry("FILM", "Film", ""),)
    grades = (CATALOG.CatalogEntry("STRETCH_FILM", "Stretch Film", ""),)
    assert merge_form_and_grade(None, "HDPE stretch film", None, forms, grades) == ("FILM", "STRETCH_FILM")


def test_pail_matches_only_when_the_master_uses_that_word() -> None:
    grades = (CATALOG.CatalogEntry("BUCKETS", "Buckets", "pails"),)
    assert merge_form_and_grade(None, "a pail of scrap", None, (), grades) == (None, None)


def test_pallet_beats_tote_when_both_are_named() -> None:
    assert merge_form_and_grade(None, "pallets and totes", None, FORM_ENTRIES, GRADE_ENTRIES)[1] == "PALLETS"


def test_vision_does_not_replace_an_ai_physical_form() -> None:
    assert merge_form_and_grade("FILM", "LDPE scrap", "REGRIND", FORM_ENTRIES, GRADE_ENTRIES) == ("FILM", None)


def test_text_grade_wins_over_a_vision_grade() -> None:
    assert merge_form_and_grade(None, "plastic pallets", "DRUMS", FORM_ENTRIES, GRADE_ENTRIES) == (None, "PALLETS")


POLYMER_ENTRIES = (
    CATALOG.CatalogEntry("PP", "PP", "", "Polypropylene"),
    CATALOG.CatalogEntry("HDPE", "HDPE", "", "High-Density Polyethylene"),
    CATALOG.CatalogEntry("HDPE_HMW", "HDPE HMW", "", "High Molecular Weight HDPE"),
    CATALOG.CatalogEntry("LDPE", "LDPE", "low density polyethylene"),
    CATALOG.CatalogEntry("LLDPE", "LLDPE", "linear low density polyethylene"),
    CATALOG.CatalogEntry("PET_HDPE", "PET/HDPE", ""),
    CATALOG.CatalogEntry("PLASTIC_PALLETS", "Plastic Pallets", ""),
    CATALOG.CatalogEntry("OTHER", "Other", ""),
)
ITEM_ENTRIES = (CATALOG.CatalogEntry("PALLETS", "Pallets", "Plastic pallets or pallet parts."),)


def test_seller_text_naming_two_polymers_keeps_both() -> None:
    assert CATALOG.match_distinct("HDPE and PP regrind", POLYMER_ENTRIES) == ("HDPE", "PP")
    assert CATALOG.match_distinct("PP / HDPE mixed caps", POLYMER_ENTRIES) == ("PP", "HDPE")
    # The single-code matcher alone would have picked one of them by label length.
    assert CATALOG.match_one("HDPE and PP regrind", POLYMER_ENTRIES) == "HDPE"


def test_seller_text_naming_one_polymer_resolves_it() -> None:
    assert CATALOG.match_distinct("Clean PP regrind", POLYMER_ENTRIES) == ("PP",)
    assert CATALOG.match_distinct("PP purge, PP lumps", POLYMER_ENTRIES) == ("PP",)
    assert CATALOG.match_distinct("mixed scrap", POLYMER_ENTRIES) == ()


def test_label_inside_a_longer_label_is_not_a_second_polymer() -> None:
    assert CATALOG.match_distinct("HDPE HMW film", POLYMER_ENTRIES) == ("HDPE_HMW",)
    assert CATALOG.match_distinct("linear low density polyethylene film", POLYMER_ENTRIES) == ("LLDPE",)
    assert CATALOG.match_distinct("HDPE HMW and HDPE drums", POLYMER_ENTRIES) == ("HDPE_HMW", "HDPE")
    assert CATALOG.match_distinct("PET/HDPE bales", POLYMER_ENTRIES) == ("PET_HDPE",)


def test_item_word_row_is_set_aside_only_beside_another_polymer() -> None:
    assert CATALOG.match_distinct("HDPE plastic pallets", POLYMER_ENTRIES, ITEM_ENTRIES) == ("HDPE",)
    assert CATALOG.match_distinct("plastic pallets", POLYMER_ENTRIES, ITEM_ENTRIES) == ("PLASTIC_PALLETS",)
    assert CATALOG.match_distinct("HDPE and PP pallets", POLYMER_ENTRIES, ITEM_ENTRIES) == ("HDPE", "PP")
    # Without the item catalog the pallet row still counts as a second code.
    assert CATALOG.match_distinct("HDPE plastic pallets", POLYMER_ENTRIES) == ("HDPE", "PLASTIC_PALLETS")
    # A vague second row is not an item word and keeps the text unresolved.
    assert CATALOG.match_distinct("HDPE and other plastics", POLYMER_ENTRIES, ITEM_ENTRIES) == ("HDPE", "OTHER")


def test_web_lead_merge_leaves_a_multi_polymer_seller_unresolved() -> None:
    source = (WEB_LEADS_MODELS / "web_lead.py").read_text(encoding="utf-8")
    assert "seller_polymers = match_distinct(" in source
    assert 'match_one(declared_material, catalog.get("polymer", ()))' not in source
    assert "if len(seller_polymers) > 1:" in source
    # The merge and the stored-evidence replay read the same seller text.
    assert source.count("_declared_material_text(") == 3
    assert "declared_material = _declared_material_text(canonical, raw)" in source
    assert "_declared_material_text(self.canonical_payload or {}, self.raw_payload or {})" in source
    assert "match_distinct(declared_material, polymer_entries" in source


def test_web_lead_merge_collects_grade_separately_from_form() -> None:
    source = (WEB_LEADS_MODELS / "web_lead.py").read_text(encoding="utf-8")
    assert "merge_form_and_grade(" in source
    assert 'merged["form"] = form_code' not in source


@pytest.mark.parametrize("lbs", [7_900.0, 8_500.0, 10_500.0])
@pytest.mark.parametrize("code", [*MATERIAL_CODES, None])
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


@pytest.mark.parametrize(
    ("token", "form_code", "grade_code"),
    [
        ("pallets,", None, "PALLETS"),
        ("crates.", None, "CRATES"),
        ("(totes)", None, "TOTES"),
        ("film.", "FILM", None),
        ("regrind,", "REGRIND", None),
        ("pal,lets", None, None),
        ("...", None, None),
    ],
)
def test_classify_material_word_strips_edge_punctuation(
    token: str, form_code: str | None, grade_code: str | None
) -> None:
    assert NORMALIZER.classify_material_word(token) == (form_code, grade_code)


def test_punctuated_pallet_phrase_meets_the_reusable_threshold() -> None:
    grades: list[str] = []
    form_code = None
    for token in " ".join("HDPE pallets, clean".split()).split():
        word_form, word_grade = NORMALIZER.classify_material_word(token)
        if word_form and form_code is None:
            form_code = word_form
        if word_grade:
            grades.append(word_grade)
    grade = next((code for code in NORMALIZER.GRADE_WORD_PRIORITY if code in grades), None)

    assert form_code is None
    assert grade == "PALLETS"
    without_grade = _eligibility(9_000.0, polymer="HDPE", grade=None)
    with_grade = _eligibility(9_000.0, polymer="HDPE", grade=grade)
    assert without_grade.eligible is False
    assert without_grade.applicable_hot_min_lbs == 10_000.0
    assert with_grade.eligible is True
    assert with_grade.applicable_hot_min_lbs == 8_000.0
    assert with_grade.policy_applied == "reusable_item"


def _profile_catalog():
    entry = CATALOG.CatalogEntry
    return {
        "polymer": (
            entry("LDPE", "LDPE", "", "Low-Density Polyethylene"),
            entry("HDPE", "HDPE", ""),
            entry("HDPE_HMW", "HDPE HMW", ""),
            entry("PET", "PET", ""),
            entry("PP", "PP", ""),
            entry("BOPP", "BOPP", ""),
            entry("PMMA", "PMMA", "", "Acrylic"),
            entry("MRP", "MRP", "", "Mixed Rigid Plastic"),
        ),
        "form": (entry("FILM", "Film", ""), entry("REGRIND", "Regrind", ""), entry("LOOSE", "Loose", "")),
        "material_grade": (entry("DRUMS", "Drums", ""), entry("BOTTLES", "Bottles", "")),
        "quality_tier": (
            entry("GRADE_A", "Grade A", ""),
            entry("GRADE_B", "Grade B", ""),
            entry("GRADE_C", "Grade C", ""),
            entry("REUSABLE", "Reusable", ""),
            entry("STANDARD", "Standard", ""),
        ),
        "color": (entry("WHITE", "White", ""), entry("MIXED", "Mixed Color", "")),
        "source_type": (entry("POST_CONSUMER", "Post-Consumer", ""),),
        "packaging": (entry("bales", "Bales", ""), entry("loose", "Loose", ""), entry("supersacks", "Supersacs", "")),
        "attribute": (
            entry("clean", "Clean", ""),
            entry("printed", "Printed", ""),
            entry("rigid", "Rigid", ""),
            entry("mixed", "Mixed", ""),
            entry("reusable", "Reusable", ""),
        ),
    }


def test_retired_forms_are_not_form_codes() -> None:
    assert "REPRO" not in FORM_CODES
    assert "LOOSE" not in FORM_CODES
    assert "REPRO" not in FORM_WORD_CODES
    assert "LOOSE" not in FORM_WORD_CODES


def test_loose_catalog_entry_is_packaging() -> None:
    catalog = _profile_catalog()
    loose = CATALOG.split_phrase("HDPE Loose", catalog)
    assert loose["polymer"] == "HDPE"
    assert loose["form"] is None
    assert loose["packaging_type"] == "loose"
    both = CATALOG.split_phrase("HDPE Loose Film", catalog)
    assert both["form"] == "FILM"
    assert both["packaging_type"] == "loose"


def test_phrase_rules_fill_profile_slots_without_a_product_row() -> None:
    catalog = _profile_catalog()

    grade_a = CATALOG.split_phrase("LDPE Film - Grade A", catalog)
    assert grade_a["polymer"] == "LDPE"
    assert grade_a["form"] == "FILM"
    assert grade_a["quality_tier"] == "GRADE_A"
    assert grade_a["packaging_type"] is None
    assert grade_a["attributes"] == ()

    hmw = CATALOG.split_phrase("HDPE-HMW Drum Regrind CLEAN", catalog)
    assert hmw["polymer"] == "HDPE_HMW"
    assert hmw["material_grade"] == "DRUMS"
    assert hmw["form"] == "REGRIND"
    assert hmw["attributes"] == ("clean",)

    bottles = CATALOG.split_phrase("PET Bottles - Post Consumer Bales", catalog)
    assert bottles["polymer"] == "PET"
    assert bottles["material_grade"] == "BOTTLES"
    assert bottles["source_type"] == "POST_CONSUMER"
    assert bottles["packaging_type"] == "bales"

    supersacs = CATALOG.split_phrase("PP Supersacs - REUSEABLE", catalog)
    assert supersacs["polymer"] == "PP"
    assert supersacs["quality_tier"] == "REUSABLE"
    assert "reusable" not in supersacs["attributes"]

    printed = CATALOG.split_phrase("BOPP Film - White W/ Print", catalog)
    assert printed["polymer"] == "BOPP"
    assert printed["form"] == "FILM"
    assert printed["color"] == "WHITE"
    assert printed["attributes"] == ("printed",)

    assert CATALOG.split_phrase("Acrylic (PMMA)", catalog)["polymer"] == "PMMA"

    rigid = CATALOG.split_phrase("Mixed Rigid Plastics - Grade A", catalog)
    assert rigid["quality_tier"] == "GRADE_A"
    assert "rigid" in rigid["attributes"]
    assert rigid["polymer"] is None

    mixed = CATALOG.split_phrase("HDPE Mixed Color Film", catalog)
    assert mixed["color"] == "MIXED"
    assert "mixed" not in mixed["attributes"]

    assert CATALOG.restrict_to_catalog({"quality_tier": "invented"}, catalog)["quality_tier"] is None
