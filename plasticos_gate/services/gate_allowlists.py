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
    }
)

# Odoo fields no converge result may ever write, whatever a row says (CTO
# decision 5). Computed, related, readonly and One2many fields are refused by
# the Odoo-side writer from the field definition itself.
CONVERGE_V2_NEVER_TARGETS = frozenset(
    {
        "id",
        "display_name",
        "create_uid",
        "create_date",
        "write_uid",
        "write_date",
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

# Field-name prefixes that are mail/activity plumbing, counts or stats, never data.
CONVERGE_V2_NEVER_TARGET_PREFIXES = ("message_", "activity_", "website_message", "rating_", "has_message")

# Cartridge fields deliberately left without a row in the partner and material
# profile tables, and why. Never requested for those targets, never written.
# (The facility profile is open by model definition; its unmapped fields are
# derived per run by ``derive_facility_profile_target``.)
CONVERGE_V2_UNMAPPED = {
    "tier": "no Odoo home; CEG-adjacent classification",
    "capacity_tons_month": "no partner or material-profile home; facility profiles map it to capacity_lbs_month",
    "material_grade": "material_grade_id is a material profile identity field, never a target",
    "material_forms": "form_id is a material profile identity field; facility form preference is not a list",
    "certifications": "no reviewed Odoo certification field to map onto",
}


def is_never_target(field_name: str) -> bool:
    """True for an Odoo field no converge result may ever write (CTO decision 5)."""
    return field_name in CONVERGE_V2_NEVER_TARGETS or field_name.startswith(CONVERGE_V2_NEVER_TARGET_PREFIXES)


def _check_never_targets() -> None:
    for target in CONVERGE_V2_TARGETS.values():
        for row in target.rows:
            if is_never_target(row.odoo_field):
                raise ValueError(f"{target.key}: {row.odoo_field} may never be a converge target")
            if row.cartridge_field in CONVERGE_V2_UNMAPPED:
                raise ValueError(f"{target.key}: {row.cartridge_field} is declared unmapped")


_check_never_targets()


# ── Facility profile: open by model definition (operator decision 2026-11-13) ─
#
# "All fields in Odoo facility profile are open to [EIE] to read and write."
# No hand-picked row list: every eligible data field of
# ``plasticos.facility.profile`` (all ``_inherit`` extensions included) is a
# candidate. Eligibility comes from the model's own field definitions, which
# the Odoo caller passes in as ``OdooFieldDef`` (this module cannot read a
# model). A cartridge field maps to the eligible Odoo field of the same name,
# or through ``FACILITY_PROFILE_V2_ALIASES`` where the names differ. Decisions
# 4 (units), 5 (never targets) and 6 (merge-not-overwrite, no master record)
# still hold.

# The plasticos cartridge's declared ``Facility`` properties (spec 0.5.0,
# EIE ``domains/plasticos/spec.yaml``). The request names each as its target
# ``type``, so a cartridge whose declaration moved is refused rather than
# answered under an unreviewed meaning.
PLASTICOS_FACILITY_DECLARATIONS = _freeze(
    {
        "facility_id": {"type": "string"},
        "name": {"type": "string"},
        "min_density": {"type": "float"},
        "max_density": {"type": "float"},
        "min_mfi": {"type": "float"},
        "max_mfi": {"type": "float"},
        "contamination_tolerance": {"type": "float"},
        "capacity_tons_month": {"type": "float"},
        "tier": {"type": "string"},
        "processed_polymers": _DECL_POLYMER_CODES,
        "city": {"type": "string"},
        "state": {"type": "string"},
        "zip_code": {"type": "string"},
        "material_grade": {"type": "string"},
        "certifications": {"type": "list", "items": {"type": "string"}},
        "street": {"type": "string"},
        "street2": {"type": "string"},
        "website": {"type": "string"},
        "email": {"type": "string"},
        "phone": {"type": "string"},
        "material_forms": {"type": "list", "items": {"type": "string"}},
    }
)
# Cartridge identity: never requested, never written.
CARTRIDGE_IDENTITY_FIELDS = frozenset({"facility_id"})

# Capacity: lb/month in Odoo (an Integer). A converted value that is not a
# whole number of pounds is skipped, never rounded (decision 4).
_LB_PER_METRIC_TON = 1000.0 / 0.45359237
_UNITS_CAPACITY = (
    ("lb/month", 1.0),
    ("lbs/month", 1.0),
    ("short_ton/month", 2000.0),
    ("t/month", _LB_PER_METRIC_TON),
    ("tonne/month", _LB_PER_METRIC_TON),
)


@dataclass(frozen=True, slots=True)
class FacilityAlias:
    odoo_field: str
    units: tuple[tuple[str, float], ...] = ()


# Only the names that differ between the cartridge and the facility profile.
FACILITY_PROFILE_V2_ALIASES = MappingProxyType(
    dict(
        (
            ("processed_polymers", FacilityAlias("accepted_polymer_ids")),
            ("min_density", FacilityAlias("density_min", _UNITS_DENSITY)),
            ("max_density", FacilityAlias("density_max", _UNITS_DENSITY)),
            ("min_mfi", FacilityAlias("melt_index_min", _UNITS_MFI)),
            ("max_mfi", FacilityAlias("melt_index_max", _UNITS_MFI)),
            ("contamination_tolerance", FacilityAlias("contamination_tolerance_pct", _UNITS_PERCENT)),
            ("capacity_tons_month", FacilityAlias("capacity_lbs_month", _UNITS_CAPACITY)),
        )
    )
)


@dataclass(frozen=True, slots=True)
class OdooFieldDef:
    """What the Odoo caller knows about one model field, as plain data."""

    name: str
    ftype: str
    relation: str | None = None
    relation_has_code: bool = False
    stored: bool = True
    computed: bool = False
    related: bool = False
    readonly: bool = False
    selection_keys: tuple[str, ...] = ()


_ODOO_TYPE_KIND = MappingProxyType(
    dict(
        (
            ("char", V2_KIND_CHAR),
            ("text", V2_KIND_CHAR),
            ("float", V2_KIND_FLOAT),
            ("integer", V2_KIND_INTEGER),
            ("boolean", V2_KIND_BOOLEAN),
            ("selection", V2_KIND_SELECTION),
            ("many2one", V2_KIND_MANY2ONE_CODE),
            ("many2many", V2_KIND_MANY2MANY_CODE),
        )
    )
)


def field_ineligibility(field_def: OdooFieldDef) -> str | None:
    """Why an Odoo field is not an eligible facility-profile data field, or None."""
    if is_never_target(field_def.name):
        return "never a converge target"
    if field_def.ftype == "one2many":
        return "one2many"
    if not field_def.stored:
        return "not stored"
    if field_def.computed:
        return "computed"
    if field_def.related:
        return "related"
    if field_def.readonly:
        return "readonly"
    kind = _ODOO_TYPE_KIND.get(field_def.ftype)
    if kind is None:
        return f"Odoo type {field_def.ftype!r} has no converge value kind"
    if kind in (V2_KIND_MANY2ONE_CODE, V2_KIND_MANY2MANY_CODE) and not (
        field_def.relation and field_def.relation_has_code
    ):
        return f"{field_def.ftype} to {field_def.relation} has no code to resolve by"
    return None


def eligible_odoo_fields(field_defs) -> MappingProxyType:
    """The eligible data fields among ``field_defs``, by name."""
    return MappingProxyType({f.name: f for f in field_defs if field_ineligibility(f) is None})


# Shared typed-syntax type tokens (EIE app/engines/spec_types.py), named so
# they are compared as constants, not as enum literals.
DECL_STRING = "string"
DECL_LIST = "list"
DECL_MAP = "map"
DECL_NUMBER_TYPES = frozenset({"float", "int", "integer", "number"})
DECL_BOOL_TYPES = frozenset({"bool", "boolean"})
_CODE_PROPERTY = "code"


def _declaration_kind_problem(declaration, kind: str) -> str | None:
    """Why a cartridge declaration cannot be written as ``kind``, or None."""
    decl_type = declaration.get("type")
    if decl_type == DECL_STRING:
        ok = kind in (V2_KIND_CHAR, V2_KIND_SELECTION, V2_KIND_MANY2ONE_CODE)
    elif decl_type in DECL_NUMBER_TYPES:
        ok = kind in V2_NUMERIC_KINDS
    elif decl_type in DECL_BOOL_TYPES:
        ok = kind == V2_KIND_BOOLEAN
    elif decl_type == DECL_LIST:
        ok = kind == V2_KIND_MANY2MANY_CODE and _list_code_key(declaration) is not False
    else:
        ok = False
    return None if ok else f"cartridge type {decl_type!r} cannot be written as {kind}"


def _list_code_key(declaration):
    """For a list declaration: None for a list of strings, 'code' for a list of {code}, else False."""
    items = declaration.get("items") or {}
    if items.get("type") == DECL_STRING:
        return None
    if items.get("type") == DECL_MAP:
        names = {p.get("name") for p in items.get("properties") or ()}
        return _CODE_PROPERTY if _CODE_PROPERTY in names else False
    return False


def derive_facility_profile_target(field_defs, declarations=None) -> tuple[ConvergeV2Target, MappingProxyType]:
    """The facility-profile target for this model's field definitions.

    Returns the target (one row per cartridge field that maps to an eligible
    Odoo field, by alias or by identical name) and the cartridge fields left
    unmapped with the reason.
    """
    declarations = PLASTICOS_FACILITY_DECLARATIONS if declarations is None else declarations
    eligible = eligible_odoo_fields(field_defs)
    every = {f.name: f for f in field_defs}
    rows = []
    unmapped = {}
    for cartridge_field, declaration in declarations.items():
        if cartridge_field in CARTRIDGE_IDENTITY_FIELDS:
            unmapped[cartridge_field] = "cartridge identity"
            continue
        alias = FACILITY_PROFILE_V2_ALIASES.get(cartridge_field)
        odoo_name = alias.odoo_field if alias else cartridge_field
        field_def = eligible.get(odoo_name)
        if field_def is None:
            if odoo_name in every:
                unmapped[cartridge_field] = f"{odoo_name}: {field_ineligibility(every[odoo_name])}"
            else:
                unmapped[cartridge_field] = "no facility-profile field of that name and no alias"
            continue
        kind = _ODOO_TYPE_KIND[field_def.ftype]
        problem = _declaration_kind_problem(declaration, kind)
        if problem:
            unmapped[cartridge_field] = f"{odoo_name}: {problem}"
            continue
        units = alias.units if alias else ()
        if kind in V2_NUMERIC_KINDS and not units:
            unmapped[cartridge_field] = f"{odoo_name}: no reviewed unit for this Odoo number"
            continue
        code_kwargs = {}
        if kind in (V2_KIND_MANY2ONE_CODE, V2_KIND_MANY2MANY_CODE):
            code_kwargs = {"code_model": field_def.relation}
            if kind == V2_KIND_MANY2MANY_CODE and _list_code_key(declaration):
                code_kwargs["code_item_key"] = _CODE_PROPERTY
        rows.append(_row(cartridge_field, odoo_name, kind, declaration, units=units, **code_kwargs))
    target = ConvergeV2Target(
        V2_TARGET_FACILITY_PROFILE,
        V2_SUBJECT_MATERIAL,
        V2_CARTRIDGE_NODE,
        "plasticos.facility.profile",
        tuple(rows),
    )
    return target, MappingProxyType(unmapped)


def resolve_v2_target(target: str, field_defs=None) -> ConvergeV2Target:
    """The converge v2 target spec: a static table, or derived for the facility profile."""
    if target == V2_TARGET_FACILITY_PROFILE:
        if field_defs is None:
            raise ValueError("the facility profile target needs the model's field definitions")
        return derive_facility_profile_target(field_defs)[0]
    return CONVERGE_V2_TARGETS[target]
