"""Intake → material profile field bridge (canonical names, no duplicate schema)."""

from __future__ import annotations

from .profile_features import compute_has_residue_feature

# Intake snapshot field → material profile ORM field (do not duplicate canonical names).
INTAKE_TO_PROFILE_VALUE_MAP = {
    "mfi_value": "melt_flow_index",
    "density_value": "density",
    "moisture_pct": "moisture_percent",
    "contamination_pct": "contamination_percent",
}

# Shared Many2one / selection / M2M fields copied by the same name on both models.
SHARED_PROFILE_SCALAR_FIELD_NAMES = (
    "polymer_id",
    "form_id",
    "color_id",
    "source_type_id",
    "origin_form_id",
    "origin_process_type",
    "filler_type_id",
    "filler_pct",
    "quantity_per_load_lbs",
    "loads_per_month",
    "lat",
    "lon",
)

SHARED_PROFILE_FIELD_NAMES = SHARED_PROFILE_SCALAR_FIELD_NAMES + ("material_attribute_ids",)

# Stored profile fields that must never be sourced from material.profile ORM reads.
FORBIDDEN_PROFILE_ORM_READ_KEYS = frozenset({"target_price", "has_residue"})

# Legacy intake keys that must not appear in bridge payloads.
FORBIDDEN_INTAKE_PAYLOAD_KEYS = frozenset(
    {
        "polymer",
        "form",
        "color",
        "material_description",
        "estimated_lbs",
        "contamination_flags",
    }
)


def _m2o_id(record, field_name):
    field = getattr(record, field_name, False)
    return field.id if field else False


def _attribute_codes(record) -> list[str]:
    attributes = getattr(record, "material_attribute_ids", None)
    if not attributes:
        return []
    codes = attributes.mapped("code")
    names = attributes.mapped("name")
    return [c for c in codes if c] + [n for n in names if n]


def _source_type_label(record) -> str | None:
    source_type = getattr(record, "source_type_id", None)
    if source_type in (None, False):
        return None
    code = getattr(source_type, "code", None) or None
    name = getattr(source_type, "name", None) or None
    return code or name


def build_material_profile_vals_from_intake(intake) -> dict:
    """ORM create/write vals: intake snapshot → plasticos.material.profile."""
    vals = {
        "melt_flow_index": getattr(intake, "mfi_value", 0) or 0,
        "density": getattr(intake, "density_value", 0) or 0,
        "moisture_percent": getattr(intake, "moisture_pct", 0) or 0,
        "contamination_percent": getattr(intake, "contamination_pct", 0) or 0,
    }
    for field_name in SHARED_PROFILE_SCALAR_FIELD_NAMES:
        if hasattr(intake, field_name):
            value = getattr(intake, field_name)
            if field_name.endswith("_id"):
                vals[field_name] = _m2o_id(intake, field_name)
            else:
                vals[field_name] = value
    attribute_ids = intake.material_attribute_ids.ids if intake.material_attribute_ids else []
    if attribute_ids:
        vals["material_attribute_ids"] = [(6, 0, attribute_ids)]
    return vals


def build_intake_to_profile_bridge_payload(intake) -> dict:
    """Canonical bridge payload for matchers/normalizers (includes derived has_residue)."""
    profile_vals = build_material_profile_vals_from_intake(intake)
    attribute_codes = _attribute_codes(intake)
    has_residue = compute_has_residue_feature(
        contamination_percent=getattr(intake, "contamination_pct", None),
        contamination_notes=getattr(intake, "contamination_notes", None),
        material_attribute_names_or_codes=attribute_codes,
        source_type_name_or_code=_source_type_label(intake),
        origin_process_type=getattr(intake, "origin_process_type", None),
        freeform_notes=getattr(intake, "intake_notes", None),
    )

    payload = {
        "polymer_id": _m2o_id(intake, "polymer_id"),
        "form_id": _m2o_id(intake, "form_id"),
        "color_id": _m2o_id(intake, "color_id"),
        "source_type_id": _m2o_id(intake, "source_type_id"),
        "origin_form_id": _m2o_id(intake, "origin_form_id"),
        "origin_process_type": getattr(intake, "origin_process_type", None),
        "material_attribute_ids": intake.material_attribute_ids.ids if intake.material_attribute_ids else [],
        "filler_type_id": _m2o_id(intake, "filler_type_id"),
        "filler_pct": getattr(intake, "filler_pct", None),
        "quantity_per_load_lbs": getattr(intake, "quantity_per_load_lbs", None),
        "loads_per_month": getattr(intake, "loads_per_month", None),
        "lat": getattr(intake, "lat", None),
        "lon": getattr(intake, "lon", None),
        "melt_flow_index": profile_vals.get("melt_flow_index"),
        "density": profile_vals.get("density"),
        "moisture_percent": profile_vals.get("moisture_percent"),
        "contamination_percent": profile_vals.get("contamination_percent"),
        "has_residue": has_residue,
    }

    payload.pop("target_price", None)
    for forbidden in FORBIDDEN_INTAKE_PAYLOAD_KEYS:
        payload.pop(forbidden, None)

    return payload
