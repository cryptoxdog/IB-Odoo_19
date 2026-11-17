"""Move retired facility equipment onto capabilities and In profiles (ADR-134 §7 and §9).

The planner is pure. The upgrade script reads the database, applies the plan,
and drops the retired columns only after the values have moved. A second run
changes nothing: a capability already recorded for the same facility, type and
details is unchanged, and an In profile whose key and windows already match is
unchanged. A key that already belongs to a different profile is a collision.
It is reported and left in place.

Writes are grouped by capability type: one create call per type.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

MIGRATION = "19.0.5.7.0"

# Equipment code -> (capability type code, detail pairs). Detail values are the
# seeded property selections (baler: hrb / downstroke).
EQUIPMENT_CAPABILITY: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "horizontal_baler": ("baling", (("baler", "hrb"),)),
    "downstroke_baler": ("baling", (("baler", "downstroke"),)),
    "shredder": ("shredding", ()),
    "granulator": ("grinding", ()),
    "wash_line": ("washing", ()),
    "pelletizer": ("pelletizing", ()),
    "extruder": ("extrusion", ()),
    "compounder": ("compounding", ()),
    "sorting_line": ("sorting", ()),
    "metal_removal": ("metal_separation", ()),
    "moisture_reduction": ("drying", ()),
}
REVIEW_EQUIPMENT = {"fr_filtration": "fr_filtration", "fines_screening": "fines_screening"}
_FORM_FROM_EQUIPMENT = (
    ("regrind", "REGRIND"),
    ("pellet", "PELLETS"),
    ("flake", "FLAKE"),
    ("rollstock", "ROLLSTOCK"),
)
_PACKAGING_FROM_EQUIPMENT = (("bales", "bales"),)
HANDLES_FORM = {
    "handles_regrind": "REGRIND",
    "handles_pellet": "PELLETS",
    "handles_flake": "FLAKE",
    "handles_rollstock": "ROLLSTOCK",
}
CAN_CAPABILITY = {
    "can_remove_metal": ("metal_separation", ()),
    "can_reduce_moisture": ("drying", ()),
}
CAN_REVIEW = {"can_filter_fr": "fr_filtration", "can_screen_fines": "fines_screening"}
PROCESS_CAPABILITY = {
    "blow_mold": "blow_molding",
    "compounding": "compounding",
    "compression_mold": "compression_molding",
    "extrusion": "extrusion",
    "film_blown": "film_blowing",
    "film_cast": "film_casting",
    "injection": "injection_molding",
    "rotomold": "rotomolding",
    "thermoform": "thermoforming",
}


@dataclass(frozen=True, slots=True)
class FacilitySnapshot:
    facility_id: int
    partner_id: int | None = None
    equipment_codes: tuple[str, ...] = ()
    handles: dict = field(default_factory=dict)
    cans: dict = field(default_factory=dict)
    process_type: str | None = None
    form_preference_code: str | None = None
    polymer_ids: tuple[int, ...] = ()
    density_min: float | None = None
    density_max: float | None = None
    melt_index_min: float | None = None
    melt_index_max: float | None = None


@dataclass(frozen=True, slots=True)
class ExistingProfile:
    profile_id: int
    partner_id: int | None
    polymer_id: int | None
    form_code: str | None
    grade_id: int | None
    direction: str | None
    density_min: float | None = None
    density_max: float | None = None
    mfi_min: float | None = None
    mfi_max: float | None = None
    form_is_repro: bool = False
    two_sided_blank: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityPlan:
    facility_id: int
    type_code: str
    details: dict
    sources: tuple[str, ...]
    sequence: int
    unchanged: bool = False

    @property
    def detail_key(self) -> str:
        return json.dumps(self.details, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class ProfilePlan:
    facility_id: int
    partner_id: int
    polymer_id: int
    form_code: str | None
    packaging_code: str | None
    direction: str
    density_min: float | None
    density_max: float | None
    mfi_min: float | None
    mfi_max: float | None
    unchanged: bool = False


@dataclass(frozen=True, slots=True)
class ReviewItem:
    facility_id: int | None
    profile_id: int | None
    reason: str
    detail: str
    collision: bool = False


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    capabilities: tuple[CapabilityPlan, ...]
    profiles: tuple[ProfilePlan, ...]
    review: tuple[ReviewItem, ...]

    def counts(self) -> dict[str, int]:
        return {
            "capabilities_created": sum(1 for row in self.capabilities if not row.unchanged),
            "capabilities_unchanged": sum(1 for row in self.capabilities if row.unchanged),
            "profiles_created": sum(1 for row in self.profiles if not row.unchanged),
            "profiles_unchanged": sum(1 for row in self.profiles if row.unchanged),
            "key_collisions": sum(1 for row in self.review if row.collision),
            "review_rows": len(self.review),
        }

    def creates_by_type(self) -> dict[str, list[CapabilityPlan]]:
        """New capability rows grouped by type, so one write serves one type."""
        grouped: dict[str, list[CapabilityPlan]] = {}
        for row in self.capabilities:
            if row.unchanged:
                continue
            grouped.setdefault(row.type_code, []).append(row)
        return grouped


def _details(pairs: tuple[tuple[str, str], ...]) -> dict:
    return dict(pairs)


def _same_window(left, right) -> bool:
    return (left or 0.0) == (right or 0.0)


def _profile_key(partner_id, polymer_id, form_code, grade_id, direction) -> tuple:
    return (partner_id, polymer_id, form_code or None, grade_id or None, direction or None)


def plan_migration(
    facilities: list[FacilitySnapshot],
    *,
    known_forms: set[str],
    existing_profiles: list[ExistingProfile] | None = None,
    existing_capabilities: set[tuple] | None = None,
) -> MigrationPlan:
    """Plan capabilities, In profiles and the review list. Nothing is written."""
    existing_profiles = existing_profiles or []
    existing_capabilities = existing_capabilities or set()
    capabilities: list[CapabilityPlan] = []
    profiles: list[ProfilePlan] = []
    review: list[ReviewItem] = []
    taken = {
        _profile_key(row.partner_id, row.polymer_id, row.form_code, row.grade_id, row.direction): row
        for row in existing_profiles
        if row.partner_id and row.polymer_id
    }

    for snapshot in facilities:
        _plan_facility(
            snapshot,
            known_forms=known_forms,
            existing_capabilities=existing_capabilities,
            taken=taken,
            capabilities=capabilities,
            profiles=profiles,
            review=review,
        )

    for row in existing_profiles:
        if row.form_is_repro:
            review.append(
                ReviewItem(
                    None,
                    row.profile_id,
                    "repro_review",
                    f"profile {row.profile_id} stays on REPRO until pellets are confirmed",
                )
            )
        if row.two_sided_blank:
            review.append(
                ReviewItem(
                    None,
                    row.profile_id,
                    "two_sided_no_direction",
                    f"profile {row.profile_id} is on a two-sided company and has no direction",
                )
            )
    return MigrationPlan(tuple(capabilities), tuple(profiles), tuple(review))


def _plan_facility(
    snapshot,
    *,
    known_forms,
    existing_capabilities,
    taken,
    capabilities,
    profiles,
    review,
) -> None:
    pending: dict[tuple, list[str]] = {}

    def add(type_code: str, details: dict, source: str) -> None:
        pending.setdefault((type_code, tuple(sorted(details.items()))), []).append(source)

    for code in snapshot.equipment_codes:
        mapped = EQUIPMENT_CAPABILITY.get(code)
        if mapped:
            add(mapped[0], _details(mapped[1]), f"equipment:{code}")
            continue
        if code in REVIEW_EQUIPMENT:
            review.append(
                ReviewItem(snapshot.facility_id, None, REVIEW_EQUIPMENT[code], f"equipment {code} has no capability")
            )
            continue
        if _lookup(_FORM_FROM_EQUIPMENT, code) or _lookup(_PACKAGING_FROM_EQUIPMENT, code):
            continue
        review.append(
            ReviewItem(snapshot.facility_id, None, "unmapped_equipment", f"equipment {code} has no capability")
        )

    for flag, mapped in CAN_CAPABILITY.items():
        if snapshot.cans.get(flag):
            add(mapped[0], _details(mapped[1]), flag)
    for flag, reason in CAN_REVIEW.items():
        if snapshot.cans.get(flag):
            review.append(ReviewItem(snapshot.facility_id, None, reason, f"{flag} has no capability"))

    process = snapshot.process_type or None
    if process in PROCESS_CAPABILITY:
        add(PROCESS_CAPABILITY[process], {}, f"process:{process}")
    elif process == "other":
        review.append(ReviewItem(snapshot.facility_id, None, "other_process", "process_type other has no capability"))
    elif process:
        review.append(
            ReviewItem(snapshot.facility_id, None, "unmapped_process", f"process_type {process} has no capability")
        )

    sequence = 10
    for (type_code, detail_pairs), sources in pending.items():
        details = dict(detail_pairs)
        key = (snapshot.facility_id, type_code, json.dumps(details, sort_keys=True, separators=(",", ":")))
        capabilities.append(
            CapabilityPlan(
                facility_id=snapshot.facility_id,
                type_code=type_code,
                details=details,
                sources=tuple(sources),
                sequence=sequence,
                unchanged=key in existing_capabilities,
            )
        )
        sequence += 10

    forms, packaging, preference = _form_signals(snapshot)
    chosen, pack, form_review = _place_forms(forms, packaging, preference, known_forms)
    if not snapshot.polymer_ids:
        if chosen:
            form_review.append(("unplaceable_form", f"form {chosen} has no accepted polymer"))
        if pack:
            form_review.append(("unplaceable_form", f"packaging {pack} has no accepted polymer"))
        chosen, pack = None, None
    for reason, detail in form_review:
        review.append(ReviewItem(snapshot.facility_id, None, reason, detail))
    if not snapshot.polymer_ids:
        return
    if not snapshot.partner_id:
        review.append(ReviewItem(snapshot.facility_id, None, "unplaceable_form", "accepted polymers have no partner"))
        return
    for polymer_id in snapshot.polymer_ids:
        _plan_profile(snapshot, polymer_id, chosen, pack, taken, profiles, review)


def _lookup(rows: tuple[tuple[str, str], ...], code: str) -> str | None:
    for key, value in rows:
        if key == code:
            return value
    return None


def _form_signals(snapshot: FacilitySnapshot) -> tuple[list[str], list[str], str | None]:
    forms: list[str] = []
    packaging: list[str] = []
    for code in snapshot.equipment_codes:
        form = _lookup(_FORM_FROM_EQUIPMENT, code)
        if form:
            forms.append(form)
        pack = _lookup(_PACKAGING_FROM_EQUIPMENT, code)
        if pack:
            packaging.append(pack)
    for flag, form in HANDLES_FORM.items():
        if snapshot.handles.get(flag):
            forms.append(form)
    if snapshot.handles.get("handles_bales"):
        packaging.append("bales")
    return list(dict.fromkeys(forms)), list(dict.fromkeys(packaging)), snapshot.form_preference_code or None


def _place_forms(forms, packaging, preference, known_forms) -> tuple[str | None, str | None, list[tuple[str, str]]]:
    review: list[tuple[str, str]] = []
    known = []
    for form in forms:
        if form in known_forms:
            known.append(form)
        else:
            review.append(("unplaceable_form", f"form {form} is not a material form"))
    chosen = None
    if preference:
        if preference not in known_forms:
            review.append(("unplaceable_form", f"form {preference} is not a material form"))
        else:
            chosen = preference
            for form in known:
                if form != preference:
                    review.append(("unplaceable_form", f"form {form} is not the preferred form"))
    elif len(known) == 1:
        chosen = known[0]
    else:
        for form in known:
            review.append(("unplaceable_form", f"form {form} is one of several forms"))
    pack = None
    if packaging == ["bales"] and chosen is None and not known:
        pack = "bales"
    else:
        for code in packaging:
            review.append(("unplaceable_form", f"packaging {code} is not the only form"))
    return chosen, pack, review


def _plan_profile(snapshot, polymer_id, form_code, packaging, taken, profiles, review) -> None:
    direction = "in"
    key = _profile_key(snapshot.partner_id, polymer_id, form_code, None, direction)
    existing = taken.get(key)
    windows = (snapshot.density_min, snapshot.density_max, snapshot.melt_index_min, snapshot.melt_index_max)
    if existing is not None:
        same = (
            _same_window(existing.density_min, windows[0])
            and _same_window(existing.density_max, windows[1])
            and _same_window(existing.mfi_min, windows[2])
            and _same_window(existing.mfi_max, windows[3])
        )
        if same:
            profiles.append(
                ProfilePlan(
                    snapshot.facility_id,
                    snapshot.partner_id,
                    polymer_id,
                    form_code,
                    packaging,
                    direction,
                    *windows,
                    unchanged=True,
                )
            )
            return
        review.append(
            ReviewItem(
                snapshot.facility_id,
                existing.profile_id,
                "key_collision",
                (
                    f"partner {snapshot.partner_id} polymer {polymer_id} form {form_code or 'empty'} "
                    f"direction {direction} is already profile {existing.profile_id}"
                ),
                collision=True,
            )
        )
        return
    profiles.append(
        ProfilePlan(
            snapshot.facility_id,
            snapshot.partner_id,
            polymer_id,
            form_code,
            packaging,
            direction,
            *windows,
        )
    )
    taken[key] = ExistingProfile(
        profile_id=0,
        partner_id=snapshot.partner_id,
        polymer_id=polymer_id,
        form_code=form_code,
        grade_id=None,
        direction=direction,
        density_min=windows[0],
        density_max=windows[1],
        mfi_min=windows[2],
        mfi_max=windows[3],
    )
