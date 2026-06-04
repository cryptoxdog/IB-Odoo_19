# ADR-005: Intake–Material Profile Delta Bridge

**Status:** Accepted  
**Date:** 2026-06-04  
**Deciders:** Igor Beylin  
**Scope:** `plasticos_material_profile/intake_delta_bridge.py`, `plasticos_material_profile/profile_features.py`, intake create/onchange, normalizer/matcher payloads  
**Related:** [ADR-004](ADR-004-intake-vs-material-profile-domain-split.md), [ADR-001](ADR-001-master-data-field-architecture.md)

## Context

ADR-004 defines **which** model owns which concepts. Implementers still need a single, testable contract for:

- Creating/updating `plasticos.material.profile` from `plasticos.intake`
- Building L9/Gate/normalizer payloads without legacy string keys
- Exposing `has_residue` without storing it on the profile

Prior code inlined profile `create()` vals in `_create_material_profile_from_intake()`, omitted supply/geo deltas, and used inconsistent quality field names across modules.

## Decision

### 1. Bridge module location

All intake → profile mapping logic lives in **`plasticos_material_profile`** (Layer 1), not in `plasticos_intake`:

| File | Responsibility |
|------|----------------|
| `intake_delta_bridge.py` | `build_material_profile_vals_from_intake()`, `build_intake_to_profile_bridge_payload()` |
| `profile_features.py` | `compute_has_residue_feature()` — pure Python, no registry |

`plasticos_intake` calls the bridge via **lazy import inside methods** (no top-level `from odoo.addons.plasticos_material_profile...` in model files).

### 2. ORM vals builder

`build_material_profile_vals_from_intake(intake)` returns `create`/`write` vals:

- Applies `INTAKE_TO_PROFILE_VALUE_MAP` for renamed floats.
- Copies `SHARED_PROFILE_FIELD_NAMES` when present on the intake record.
- Sets `material_attribute_ids` as `[(6, 0, ids)]` when non-empty.
- Caller adds `partner_id` (facility) and optional `packaging_type_id`.

### 3. Bridge payload builder

`build_intake_to_profile_bridge_payload(intake)` returns a JSON-safe dict for normalizers/matchers:

**Required profile-aligned keys:**  
`polymer_id`, `form_id`, `color_id`, `source_type_id`, `origin_form_id`, `origin_process_type`, `material_attribute_ids`, `filler_type_id`, `filler_pct`, `quantity_per_load_lbs`, `loads_per_month`, `lat`, `lon`, `melt_flow_index`, `density`, `moisture_percent`, `contamination_percent`.

**Derived feature (payload only):**  
`has_residue` — boolean from `compute_has_residue_feature()`, never read from `material.profile` ORM.

**Forbidden in payload:**  
`target_price`; legacy keys `polymer`, `form`, `color`, `material_description`, `estimated_lbs`, `contamination_flags`.

**Forbidden ORM reads from profile:**  
`target_price`, `has_residue` (constants: `FORBIDDEN_PROFILE_ORM_READ_KEYS`).

### 4. Naming map (single source of truth)

```python
INTAKE_TO_PROFILE_VALUE_MAP = {
    "mfi_value": "melt_flow_index",
    "density_value": "density",
    "moisture_pct": "moisture_percent",
    "contamination_pct": "contamination_percent",
}
```

Do not add parallel profile fields using intake names.

### 5. Derived residue algorithm

`compute_has_residue_feature()` returns `True` when any signal matches:

1. `contamination_percent > 0`
2. Residue markers in `contamination_notes` or `freeform_notes` (e.g. residue, grease, adhesive)
3. Material attribute codes/names containing `residue` or in allowlist (`with_residue`, `oil_residue`, …)
4. `source_type` / `origin_process_type` text containing `residue`

Otherwise `False`. **No** stored `has_residue` column on `plasticos.material.profile`.

### 6. Material profile schema deltas (2026-06-04)

Added to `plasticos.material.profile` for reusable supply/geo:

| Field | Type | Notes |
|-------|------|-------|
| `quantity_per_load_lbs` | Float | Typical per-load weight |
| `loads_per_month` | Integer | Stored expected loads (replaces volume-derived compute) |
| `lat` | Float, digits (10,7) | Reusable geo |
| `lon` | Float, digits (10,7) | Reusable geo |

Migration `19.0.5.9.0` rounds legacy float `loads_per_month` and backfills `quantity_per_load_lbs` from `avg_lot_size_lbs` where empty.

### 7. Tests

| Test file | Tier |
|-----------|------|
| `tests/test_material_profile_intake_delta_bridge_pure.py` | Pure Python (12 tests) — mapping, residue, payload |
| `tests/contracts/test_material_profile_intake_delta_contract.py` | Post-install — field existence on profile |

Tests assert **behavior and field metadata**, not grep of source strings.

## Consequences

### Positive

- One import path for agents and services extending intake→profile sync.
- CI can run pure tests without Odoo for mapping/regression safety.
- Payloads stay canonical for Gate/CEG consumers.

### Negative / constraints

- Normalizer `_assemble_material_profile_block()` still uses legacy `form`/`color` codes on profile until separately refactored — new work should call bridge payload shape.
- Removing volume-derived `loads_per_month` compute changes UX: profile `loads_per_month` is now supplier-declared, not `monthly_volume / avg_lot`.

## Compliance

1. Extend bridge maps in `intake_delta_bridge.py` — do not duplicate mapping in intake, web_leads, or normalizer.
2. Add pure tests for any new mapped field or derived signal.
3. Bump `plasticos_material_profile` manifest patch version when profile schema changes.

## References

- `plasticos_material_profile/intake_delta_bridge.py`
- `plasticos_material_profile/profile_features.py`
- `plasticos_intake/models/intake.py` — `_create_material_profile_from_intake`, `_onchange_material_profile`
