"""Quality tier codes match their seed, and retired letters map onto that seed.

``plasticos_material_profile/quality_tier_codes.py`` is the registry.
``data/material_quality_tier_data.xml`` is the seed. Both profile-to-intake
copy paths carry the tier. Pure: reads those files only; the copy-path bodies
are compiled from source without importing Odoo.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

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


def _method(path: Path, name: str):
    """Compile one method body from ``path`` with its decorators stripped."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            node.decorator_list = []
            module = ast.Module(body=[node], type_ignores=[])
            namespace: dict = {}
            exec(compile(module, str(path), "exec"), namespace)
            return namespace[name]
    raise AssertionError(f"{name} not found in {path}")


class _Many:
    def __init__(self, ids=()):
        self.ids = list(ids)

    def __bool__(self):
        return bool(self.ids)


_PROFILE_FIELDS = {
    "polymer_id": False,
    "form_id": False,
    "source_type_id": False,
    "material_grade_id": False,
    "packaging_type_id": False,
    "quality_tier_id": False,
    "filler_type_id": False,
    "color_ids": _Many(),
    "material_attribute_ids": _Many(),
    "melt_flow_index": 0,
    "density": 0,
    "moisture_percent": 0,
    "contamination_percent": 0,
    "filler_pct": 0,
    "origin_process_type": False,
    "lat": 0,
    "lon": 0,
    "loads_per_month": 0,
    "quantity_per_load_lbs": 0,
}


class _Profile(SimpleNamespace):
    def __getitem__(self, name):
        return getattr(self, name)


def _profile(**values) -> _Profile:
    return _Profile(id=11, **{**_PROFILE_FIELDS, **values})


def test_crm_conversion_snapshot_copies_the_profile_quality_tier() -> None:
    snapshot = _method(
        ROOT / "plasticos_crm_bridge" / "models" / "crm_lead.py", "_intake_snapshot_from_material_profile"
    )
    tier = SimpleNamespace(id=4)
    assert snapshot(None, _profile(quality_tier_id=tier))["quality_tier_id"] == 4
    assert "quality_tier_id" not in snapshot(None, _profile())


def test_intake_profile_onchange_copies_the_quality_tier_and_keeps_it_when_unset() -> None:
    onchange = _method(ROOT / "plasticos_intake" / "models" / "intake.py", "_onchange_material_profile")
    tier = SimpleNamespace(id=4)
    intake = SimpleNamespace(
        material_profile_id=_profile(quality_tier_id=tier),
        **dict.fromkeys(
            (
                "polymer_id",
                "form_id",
                "source_type_id",
                "material_grade_id",
                "packaging_type_id",
                "quality_tier_id",
                "filler_type_id",
                "origin_process_type",
            ),
            False,
        ),
        **dict.fromkeys(
            ("mfi_value", "density_value", "moisture_pct", "contamination_pct", "filler_pct", "lat", "lon"), 0
        ),
    )
    onchange(intake)
    assert intake.quality_tier_id == 4

    kept = SimpleNamespace(id=5)
    intake.quality_tier_id = kept
    intake.material_profile_id = _profile()
    onchange(intake)
    assert intake.quality_tier_id is kept


def test_create_intake_action_defaults_the_profile_quality_tier() -> None:
    action = _method(ROOT / "plasticos_intake" / "models" / "material_profile_intake.py", "action_create_intake")
    tier = SimpleNamespace(id=4)
    profile = _profile(
        quality_tier_id=tier,
        partner_id=SimpleNamespace(id=3, parent_id=False),
        polymer_id=SimpleNamespace(id=1),
        ensure_one=lambda: None,
    )
    assert action(profile)["context"]["default_quality_tier_id"] == 4
    profile.quality_tier_id = False
    assert action(profile)["context"]["default_quality_tier_id"] is False
