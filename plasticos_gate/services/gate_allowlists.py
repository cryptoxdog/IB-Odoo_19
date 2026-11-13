"""Field allowlists and mappings for Odoo <-> Gate payloads."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from types import MappingProxyType

PARTNER_SNAPSHOT_FIELD_MAP = {
    "name": "name",
    "website": "website",
    "city": "city",
    "zip": "zip",
    "street": "street",
    "street2": "street2",
    "comment": "comment",
    "email": "email",
    "phone": "phone",
}

PARTNER_WRITEBACK_FIELD_ALLOWLIST = {
    "name",
    "website",
    "city",
    "zip",
    "street",
    "street2",
    "email",
    "phone",
}

WEB_LEAD_SEED_FIELD_MAP = {
    "company_name": "company",
    "contact_name": "contact",
    "contact_email": "email",
    "contact_phone": "phone",
    "material_description": "material_desc",
    "quantity_text": "quantity_text",
    "contaminant_notes": "contaminants",
}

WEB_LEAD_WRITEBACK_FIELD_MAP = {
    "company": "company_name",
    "contact": "contact_name",
    "email": "contact_email",
    "phone": "contact_phone",
    "material_desc": "material_description",
    "quantity_text": "quantity_text",
}

INTAKE_SNAPSHOT_FIELD_MAP = {
    "quantity_per_load_lbs": "quantity_per_load_lbs",
    "contamination_pct": "contamination_pct",
    "mfi_value": "mfi",
    "lat": "lat",
    "lon": "lon",
}

INTAKE_WRITEBACK_FIELD_MAP = {
    "quantity_per_load_lbs": "quantity_per_load_lbs",
    "contamination_pct": "contamination_pct",
    "mfi": "mfi_value",
}

MATCH_RESULT_FIELD_MAP = {
    "buyer_partner_id": "buyer_id",
    "score": "match_score",
    "reason": "match_reason",
    "typical_price": "typical_price",
}


# ── Converge v2: the declarative cartridge-field → Odoo-field table ─────────
#
# ADR-012 (amendment 2026-11-13) makes this table the converge v2 writeback
# allowlist. A cartridge field with no row is requested from nobody and written
# nowhere. Adding a row is a reviewed change to this file, its tests and ADR-012.
# The v1 ``PARTNER_WRITEBACK_FIELD_ALLOWLIST`` above is unchanged and still
# governs every v1 run.

# Value kinds an Odoo field may be written as. A many2one / many2many "by code"
# row resolves the code to an existing master record; it never creates one.
V2_KIND_CHAR = "char"
V2_KIND_FLOAT = "float"
V2_KIND_INTEGER = "integer"
V2_KIND_BOOLEAN = "boolean"
V2_KIND_SELECTION = "selection"
V2_KIND_MANY2ONE_CODE = "many2one_code"
V2_KIND_MANY2MANY_CODE = "many2many_code"
V2_KINDS = frozenset(
    {
        V2_KIND_CHAR,
        V2_KIND_FLOAT,
        V2_KIND_INTEGER,
        V2_KIND_BOOLEAN,
        V2_KIND_SELECTION,
        V2_KIND_MANY2ONE_CODE,
        V2_KIND_MANY2MANY_CODE,
    }
)
V2_NUMERIC_KINDS = frozenset({V2_KIND_FLOAT, V2_KIND_INTEGER})

# Declarations as the plasticos cartridge (0.5.0, node Facility) states them, in
# the shared typed syntax. The request names them as each target's `type`, so a
# cartridge whose declaration has moved is refused (`target_type_mismatch`)
# rather than answered under a meaning this table was not reviewed against.
_DECL_STRING = {"type": "string"}
_DECL_FLOAT = {"type": "float"}
_DECL_POLYMER_CODES = {
    "type": "list",
    "items": {"type": "map", "properties": [{"name": "code", "type": "string", "required": True}]},
}

# Units each numeric Odoo field accepts, with the factor that converts a value
# stated in that unit into the Odoo field's own unit. A value whose response
# does not state one of these units is skipped and recorded, never converted by
# assumption (CTO decision 4).
# Pairs, not dict literals: unit strings are not enum values (repo convention,
# see gate_config.GateAvailabilityVerdict.as_dict).
_UNITS_DENSITY = (("g/cm3", 1.0), ("g/cm³", 1.0), ("g/cc", 1.0))
_UNITS_MFI = (("g/10min", 1.0), ("g/10 min", 1.0))
_UNITS_PERCENT = (("percent", 1.0), ("%", 1.0), ("fraction", 100.0))


@dataclass(frozen=True, slots=True)
class ConvergeV2FieldRow:
    """One reviewed (cartridge field -> Odoo field) mapping.

    ``declaration`` is the cartridge's typed declaration the row was reviewed
    against; ``units`` maps each accepted stated unit to the factor that turns a
    value in that unit into the Odoo field's own unit. Code rows resolve
    ``code_field`` on ``code_model`` (inside ``code_scope_field`` of the target
    record when set); a list-of-maps value carries the code under ``code_item_key``.
    """

    cartridge_field: str
    odoo_field: str
    kind: str
    declaration: MappingProxyType = field(hash=False)
    units: MappingProxyType = field(default=MappingProxyType({}), hash=False)
    code_model: str | None = None
    code_field: str = "code"
    code_scope_field: str | None = None
    code_item_key: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in V2_KINDS:
            raise ValueError(f"unknown converge v2 value kind: {self.kind!r}")
        if self.kind in V2_NUMERIC_KINDS and not self.units:
            raise ValueError(f"numeric row {self.cartridge_field!r} must declare the units it accepts")
        if self.kind in (V2_KIND_MANY2ONE_CODE, V2_KIND_MANY2MANY_CODE) and not self.code_model:
            raise ValueError(f"code row {self.cartridge_field!r} must name the master model")

    def declaration_dict(self) -> dict:
        """A fresh, mutable copy of the declaration for a request body."""
        return copy.deepcopy(_thaw(self.declaration))


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _thaw(value):
    if isinstance(value, MappingProxyType | dict):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, tuple | list):
        return [_thaw(v) for v in value]
    return value


def _row(cartridge_field, odoo_field, kind, declaration, *, units=None, **kwargs) -> ConvergeV2FieldRow:
    return ConvergeV2FieldRow(
        cartridge_field,
        odoo_field,
        kind,
        _freeze(declaration),
        MappingProxyType(dict(units or {})),
        **kwargs,
    )


@dataclass(frozen=True, slots=True)
class ConvergeV2Target:
    """One Odoo record kind a converge v2 run may enrich."""

    key: str
    subject_type: str
    node: str
    odoo_model: str
    rows: tuple[ConvergeV2FieldRow, ...]

    def __post_init__(self) -> None:
        names = [row.cartridge_field for row in self.rows]
        if len(names) != len(set(names)):
            raise ValueError(f"target {self.key!r} maps a cartridge field twice")
        odoo_fields = [row.odoo_field for row in self.rows]
        if len(odoo_fields) != len(set(odoo_fields)):
            raise ValueError(f"target {self.key!r} maps an Odoo field twice")

    def row(self, cartridge_field: str) -> ConvergeV2FieldRow | None:
        return next((row for row in self.rows if row.cartridge_field == cartridge_field), None)


V2_TARGET_PARTNER = "partner"
V2_TARGET_MATERIAL_PROFILE = "material_profile"
V2_TARGET_FACILITY_PROFILE = "facility_profile"

V2_SUBJECT_FACILITY = "facility"
V2_SUBJECT_MATERIAL = "material"
V2_CARTRIDGE_NODE = "Facility"

CONVERGE_V2_TARGETS = MappingProxyType(
    {
        V2_TARGET_PARTNER: ConvergeV2Target(
            V2_TARGET_PARTNER,
            V2_SUBJECT_FACILITY,
            V2_CARTRIDGE_NODE,
            "res.partner",
            (
                _row("name", "name", V2_KIND_CHAR, _DECL_STRING),
                _row("city", "city", V2_KIND_CHAR, _DECL_STRING),
                _row("zip_code", "zip", V2_KIND_CHAR, _DECL_STRING),
                _row("street", "street", V2_KIND_CHAR, _DECL_STRING),
                _row("street2", "street2", V2_KIND_CHAR, _DECL_STRING),
                _row("website", "website", V2_KIND_CHAR, _DECL_STRING),
                _row("email", "email", V2_KIND_CHAR, _DECL_STRING),
                _row("phone", "phone", V2_KIND_CHAR, _DECL_STRING),
                # A state code is resolved only inside the partner's own country; a
                # partner with no country leaves it unresolved (never guessed).
                _row(
                    "state",
                    "state_id",
                    V2_KIND_MANY2ONE_CODE,
                    _DECL_STRING,
                    code_model="res.country.state",
                    code_scope_field="country_id",
                ),
            ),
        ),
        V2_TARGET_MATERIAL_PROFILE: ConvergeV2Target(
            V2_TARGET_MATERIAL_PROFILE,
            V2_SUBJECT_MATERIAL,
            V2_CARTRIDGE_NODE,
            "plasticos.material.profile",
            (
                _row("min_density", "density_min", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_DENSITY),
                _row("max_density", "density_max", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_DENSITY),
                _row("min_mfi", "mfi_min", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_MFI),
                _row("max_mfi", "mfi_max", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_MFI),
            ),
        ),
        V2_TARGET_FACILITY_PROFILE: ConvergeV2Target(
            V2_TARGET_FACILITY_PROFILE,
            V2_SUBJECT_MATERIAL,
            V2_CARTRIDGE_NODE,
            "plasticos.facility.profile",
            (
                _row(
                    "processed_polymers",
                    "accepted_polymer_ids",
                    V2_KIND_MANY2MANY_CODE,
                    _DECL_POLYMER_CODES,
                    code_model="plasticos.polymer",
                    code_item_key="code",
                ),
                _row("min_density", "density_min", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_DENSITY),
                _row("max_density", "density_max", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_DENSITY),
                _row("min_mfi", "melt_index_min", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_MFI),
                _row("max_mfi", "melt_index_max", V2_KIND_FLOAT, _DECL_FLOAT, units=_UNITS_MFI),
                _row(
                    "contamination_tolerance",
                    "contamination_tolerance_pct",
                    V2_KIND_FLOAT,
                    _DECL_FLOAT,
                    units=_UNITS_PERCENT,
                ),
            ),
        ),
    }
)

# Odoo fields no converge result may ever write, whatever a row says (CTO
# decision 5). Computed, related, readonly and One2many fields are refused by
# the Odoo-side writer from the field definition itself.
CONVERGE_V2_NEVER_TARGETS = frozenset(
    {
        "partner_id",
        "company_id",
        "active",
        "polymer_id",
        "form_id",
        "material_grade_id",
        "facility_profile_id",
        "crm_lead_id",
        "lat",
        "lon",
        "partner_latitude",
        "partner_longitude",
    }
)

# Cartridge fields deliberately left without a row, and why. Never requested,
# never written.
CONVERGE_V2_UNMAPPED = {
    "tier": "no Odoo home; CEG-adjacent classification",
    "capacity_tons_month": "the cartridge declares no unit; Odoo stores capacity in lb/month",
    "material_grade": "material_grade_id is a material profile identity field, never a target",
    "material_forms": "form_id is a material profile identity field; facility form preference is not a list",
    "certifications": "no reviewed Odoo certification field to map onto",
}


def _check_never_targets() -> None:
    for target in CONVERGE_V2_TARGETS.values():
        for row in target.rows:
            if row.odoo_field in CONVERGE_V2_NEVER_TARGETS:
                raise ValueError(f"{target.key}: {row.odoo_field} may never be a converge target")
            if row.cartridge_field in CONVERGE_V2_UNMAPPED:
                raise ValueError(f"{target.key}: {row.cartridge_field} is declared unmapped")


_check_never_targets()
