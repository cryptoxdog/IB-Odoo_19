"""Quality tier codes match their seed, and retired letters map onto that seed.

``plasticos_material_profile/quality_tier_codes.py`` is the registry.
``data/material_quality_tier_data.xml`` is the seed. Pure: reads those files only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from defusedxml import ElementTree

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "plasticos_material_profile"


def _load():
    spec = importlib.util.spec_from_file_location("plasticos_quality_tier_codes", PROFILE / "quality_tier_codes.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _seed() -> dict[str, dict[str, str]]:
    records = {}
    for record in ElementTree.parse(PROFILE / "data" / "material_quality_tier_data.xml").iter("record"):
        if record.get("model") != "plasticos.material.quality.tier":
            continue
        values = {field.get("name"): (field.text or "").strip() for field in record.findall("field")}
        records[record.get("id")] = values
    return records


TIERS = _load()


def test_quality_tier_codes_equal_the_seed_in_order() -> None:
    seed = _seed()
    assert [values["code"] for values in seed.values()] == list(TIERS.QUALITY_TIER_CODES)


def test_quality_tier_xmlids_carry_the_code() -> None:
    seed = _seed()
    assert sorted(seed) == sorted(f"quality_tier_{code.lower()}" for code in TIERS.QUALITY_TIER_CODES)


def test_quality_tier_names() -> None:
    names = {values["code"]: values["name"] for values in _seed().values()}
    assert names == {
        "GRADE_A": "Grade A",
        "GRADE_B": "Grade B",
        "GRADE_C": "Grade C",
        "REUSABLE": "Reusable",
        "STANDARD": "Standard",
    }


def test_grade_templates_reference_seeded_quality_tiers() -> None:
    tier_ids = set(_seed())
    for record in ElementTree.parse(PROFILE / "data" / "grade_template_data.xml").iter("record"):
        for field in record.findall("field"):
            if field.get("name") == "quality_tier_id":
                assert field.get("ref") in tier_ids, record.get("id")
            assert field.get("name") != "quality_tier"


def test_letter_wins_over_the_old_selection_and_other_text_is_kept() -> None:
    assert TIERS.profile_quality_tier("standard", "A") == ("GRADE_A", None)
    assert TIERS.profile_quality_tier("prime", "C") == ("GRADE_C", None)
    assert TIERS.profile_quality_tier("standard", None) == ("STANDARD", None)
    assert TIERS.profile_quality_tier("grade_b", "") == ("GRADE_B", None)
    assert TIERS.profile_quality_tier("prime", None) == (None, None)
    assert TIERS.profile_quality_tier("near_prime", "supersac") == (None, "supersac")
    assert TIERS.profile_quality_tier("economy", "unknown") == (None, "unknown")
    assert TIERS.profile_quality_tier("unknown", "  B  ") == ("GRADE_B", None)


def test_template_selection_keeps_only_the_surviving_keys() -> None:
    assert TIERS.template_quality_tier_code("grade_a") == "GRADE_A"
    assert TIERS.template_quality_tier_code(" standard ") == "STANDARD"
    assert TIERS.template_quality_tier_code("prime") is None
    assert TIERS.template_quality_tier_code("economy") is None
    assert TIERS.template_quality_tier_code(None) is None


def test_leftover_text_is_appended_once() -> None:
    assert TIERS.notes_with_leftover(None, "supersac") == "supersac"
    assert TIERS.notes_with_leftover("already there", "supersac") == "already there\nsupersac"
    assert TIERS.notes_with_leftover("PP Supersac note", "supersac") is None
    assert TIERS.notes_with_leftover("supersac", "  ") is None
    assert TIERS.notes_with_leftover("", None) is None
