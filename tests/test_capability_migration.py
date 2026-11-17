"""ADR-134 §9: equipment and templates become capabilities; polymers become In profiles."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "capability_migration_under_test",
    ROOT / "plasticos_facility_profile" / "capability_migration.py",
)
migration = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = migration
_SPEC.loader.exec_module(migration)

KNOWN_FORMS = {"FILM", "REGRIND", "PELLETS", "FLAKE", "ROLLSTOCK"}
# Stored fields of the eight former templates. The recycler description is not a source.
_TEMPLATE_SHAPES = {
    "RECYCLER": {
        "equipment_codes": (),
        "handles": {"handles_bales": True, "handles_regrind": True, "handles_pellet": True, "handles_flake": True},
    },
    "GRINDER": {
        "equipment_codes": ("granulator",),
        "handles": {"handles_bales": True, "handles_regrind": True},
    },
    "MRF": {
        "equipment_codes": ("sorting_line", "horizontal_baler"),
        "handles": {"handles_bales": True},
    },
    "COMPOUNDER": {
        "equipment_codes": ("extruder", "compounder", "pelletizer"),
        "handles": {"handles_regrind": True, "handles_pellet": True},
    },
    "FILM_PROCESSOR": {
        "equipment_codes": ("extruder", "pelletizer"),
        "handles": {"handles_bales": True, "handles_rollstock": True, "handles_pellet": True},
        "cans": {"can_reduce_moisture": True},
        "form_preference_code": "FILM",
    },
    "INJECTION_MOLDER": {
        "handles": {"handles_regrind": True, "handles_pellet": True},
        "form_preference_code": "PELLETS",
    },
    "BLOW_MOLDER": {
        "handles": {"handles_regrind": True, "handles_pellet": True},
        "form_preference_code": "PELLETS",
    },
    "BROKER": {
        "handles": {"handles_bales": True, "handles_regrind": True, "handles_pellet": True},
    },
}


def _template(code, facility_id):
    shape = _TEMPLATE_SHAPES[code]
    return migration.FacilitySnapshot(
        facility_id=facility_id,
        partner_id=facility_id,
        equipment_codes=tuple(shape.get("equipment_codes", ())),
        handles=dict(shape.get("handles", {})),
        cans=dict(shape.get("cans", {})),
        form_preference_code=shape.get("form_preference_code"),
    )


WORKED_EXAMPLE_TYPES = {
    "border": ("shredding", "metal_separation", "grinding"),
    "solvent": ("shredding", "grinding", "washing", "pelletizing"),
    "three_lines": ("shredding", "shredding", "shredding"),
    "v60_mrf": ("baling",),
}


def _plan(facilities, profiles=None, done=None):
    return migration.plan_migration(
        facilities,
        known_forms=KNOWN_FORMS,
        existing_profiles=profiles or [],
        existing_capabilities=done or set(),
    )


def _types(plan, facility_id):
    return [row.type_code for row in plan.capabilities if row.facility_id == facility_id]


def test_eight_template_shapes_become_the_mapped_capabilities():
    expected = {
        "RECYCLER": [],
        "GRINDER": ["grinding"],
        "MRF": ["sorting", "baling"],
        "COMPOUNDER": ["extrusion", "compounding", "pelletizing"],
        "FILM_PROCESSOR": ["extrusion", "pelletizing", "drying"],
        "INJECTION_MOLDER": [],
        "BLOW_MOLDER": [],
        "BROKER": [],
    }
    snapshots = [_template(code, index) for index, code in enumerate(expected, start=1)]
    plan = _plan(snapshots)
    for snapshot, code in zip(snapshots, expected, strict=True):
        assert _types(plan, snapshot.facility_id) == expected[code]
    assert plan.counts()["profiles_created"] == 0
    assert plan.counts()["capabilities_created"] == 9
    mrf = next(row for row in plan.capabilities if row.type_code == "baling")
    assert mrf.details == {"baler": "hrb"}


def test_each_process_type_maps_per_the_table():
    facilities = []
    for index, process in enumerate(migration.PROCESS_CAPABILITY, start=1):
        facilities.append(migration.FacilitySnapshot(facility_id=index, partner_id=index, process_type=process))
    facilities.append(migration.FacilitySnapshot(facility_id=99, partner_id=99, process_type="other"))
    plan = _plan(facilities)
    for facility, (_process, type_code) in zip(plan.capabilities, migration.PROCESS_CAPABILITY.items(), strict=True):
        assert facility.type_code == type_code
    reasons = {row.reason for row in plan.review if row.facility_id == 99}
    assert reasons == {"other_process"}


def test_review_list_covers_the_adr_cases():
    facility = migration.FacilitySnapshot(
        facility_id=1,
        partner_id=1,
        equipment_codes=("fr_filtration", "fines_screening"),
        cans={"can_filter_fr": True, "can_screen_fines": True},
        process_type="other",
        handles={"handles_regrind": True, "handles_pellet": True},
        polymer_ids=(7,),
        density_min=0.91,
        melt_index_max=4.0,
    )
    existing = [
        migration.ExistingProfile(
            profile_id=50,
            partner_id=1,
            polymer_id=7,
            form_code=None,
            grade_id=None,
            direction="in",
            density_min=0.5,
            form_is_repro=True,
            two_sided_blank=True,
        )
    ]
    plan = _plan([facility], existing)
    reasons = {row.reason for row in plan.review}
    assert {
        "fr_filtration",
        "fines_screening",
        "other_process",
        "unplaceable_form",
        "key_collision",
        "repro_review",
        "two_sided_no_direction",
    } <= reasons
    assert plan.counts()["profiles_created"] == 0
    assert plan.counts()["key_collisions"] == 1
    assert any("profile 50 stays on REPRO" in row.detail for row in plan.review)


def test_in_profiles_carry_form_and_windows_and_a_second_plan_is_unchanged():
    facility = migration.FacilitySnapshot(
        facility_id=3,
        partner_id=8,
        equipment_codes=("granulator",),
        handles={"handles_regrind": True},
        polymer_ids=(4, 5),
        density_min=0.9,
        density_max=0.97,
        melt_index_min=0.2,
        melt_index_max=8.0,
    )
    first = _plan([facility])
    assert first.counts()["profiles_created"] == 2
    assert {row.form_code for row in first.profiles} == {"REGRIND"}
    assert {row.direction for row in first.profiles} == {"in"}
    assert first.profiles[0].density_min == 0.9
    assert first.profiles[0].mfi_max == 8.0
    done = {(row.facility_id, row.type_code, row.detail_key) for row in first.capabilities}
    existing = [
        migration.ExistingProfile(
            profile_id=index,
            partner_id=row.partner_id,
            polymer_id=row.polymer_id,
            form_code=row.form_code,
            grade_id=None,
            direction=row.direction,
            density_min=row.density_min,
            density_max=row.density_max,
            mfi_min=row.mfi_min,
            mfi_max=row.mfi_max,
        )
        for index, row in enumerate(first.profiles, start=1)
    ]
    second = _plan([facility], existing, done)
    assert second.counts()["capabilities_created"] == 0
    assert second.counts()["capabilities_unchanged"] == 1
    assert second.counts()["profiles_created"] == 0
    assert second.counts()["profiles_unchanged"] == 2


def test_writes_are_grouped_by_capability_type():
    facilities = [
        migration.FacilitySnapshot(facility_id=1, equipment_codes=("horizontal_baler", "downstroke_baler")),
        migration.FacilitySnapshot(facility_id=2, equipment_codes=("shredder",)),
    ]
    grouped = _plan(facilities).creates_by_type()
    assert set(grouped) == {"baling", "shredding"}
    assert [row.details["baler"] for row in grouped["baling"]] == ["hrb", "downstroke"]
    assert len(grouped["shredding"]) == 1


def test_worked_example_types_are_capability_codes_the_migration_can_name():
    named = {type_code for type_code, _details in migration.EQUIPMENT_CAPABILITY.values()}
    named.update(migration.PROCESS_CAPABILITY.values())
    for example, sequence in WORKED_EXAMPLE_TYPES.items():
        assert set(sequence) <= named, example
