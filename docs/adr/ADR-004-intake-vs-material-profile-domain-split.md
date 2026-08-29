# ADR-004: Intake vs Material Profile Domain Split

**Status:** Accepted  
**Date:** 2026-06-04  
**Deciders:** Igor Beylin  
**Scope:** `plasticos_intake`, `plasticos_material_profile`, downstream bridges (offer, transaction, normalizer, buyer_match_engine)  
**Related:** [ADR-001](ADR-001-master-data-field-architecture.md), [ADR-005](ADR-005-intake-material-profile-delta-bridge.md), [ARCHITECTURE.md](../../ARCHITECTURE.md)

## Context

PlasticOS captures supplier material in two places that evolved together:

- **`plasticos.intake`** — transactional pipeline record (matching, offers, status, contacts).
- **`plasticos.material.profile`** — reusable material specification tied to a facility partner.

Without an explicit boundary, agents and integrations duplicate fields (`mfi_value` vs `melt_flow_index`), promote commercial drift (`target_price`) onto the canonical profile, or store derived intelligence (`has_residue`) as permanent schema on both models.

The brokerage flow is **intake-first**: every deal starts on an intake, but matching and repeat supply depend on a stable profile per facility + polymer + form.

## Decision

### 1. Two models, two roles

| Model | Role | Owns |
|-------|------|------|
| **`plasticos.intake`** | Transactional / load-specific capture | Workflow `status`, `facility_id`, `contact_id`, `match_line_ids`, `offer_count`, `material_profile_id` link, negotiation-time snapshots, instance-level quality readings |
| **`plasticos.material.profile`** | Canonical reusable material spec | Master-linked identity (`polymer_id`, `form_id`, `color_id`, `source_type_id`), recurring supply (`quantity_per_load_lbs`, `loads_per_month`), reusable geo (`lat`, `lon`), canonical quality names (`melt_flow_index`, `density`, `moisture_percent`, `contamination_percent`) |

Intake **may** reference a profile (`material_profile_id`) and **snapshots** fields for the active load. The profile **does not** reference a specific intake.

### 2. Module ownership

| Concern | Owner module |
|---------|----------------|
| Master registries (polymer, form, color, source) | `plasticos_material_profile` |
| `plasticos.material.profile` model + views | `plasticos_material_profile` |
| `plasticos.intake` model + pipeline actions | `plasticos_intake` |
| Intake-specific extensions on profile (intake count, “create intake” actions) | `plasticos_intake` via inheritance on `plasticos.material.profile` |
| Field bridge (intake → profile vals / payload) | `plasticos_material_profile/intake_delta_bridge.py` |

**Dependency rule:** `plasticos_material_profile` must not depend on `plasticos_intake`. Intake depends on material profile; bridge helpers live in the lower layer.

### 3. Fields that stay intake-only

Do **not** add these to `plasticos.material.profile`:

- `target_price` — commercial negotiation drift; sellers ask for quotes, not canonical target prices.
- `status`, `match_line_ids`, `offer_count` — workflow.
- `contact_id`, `facility_id` (as intake context) — operational routing; profile uses `partner_id` (facility).
- `material_profile_id` — link direction is intake → profile only.

### 4. Fields shared by name (aligned semantics)

These exist on **both** models with the same meaning and are copied across the bridge:

`polymer_id`, `form_id`, `color_id`, `source_type_id`, `origin_form_id`, `origin_process_type`, `material_attribute_ids`, `filler_type_id`, `filler_pct`, `quantity_per_load_lbs`, `loads_per_month`, `lat`, `lon`.

`source_type_id` is **required** in bridge payloads and profile alignment logic (not optional enrichment).

### 5. Intake snapshot names vs profile canonical names

On intake only — map on bridge, never duplicate on profile:

| Intake field | Profile field |
|--------------|---------------|
| `mfi_value` | `melt_flow_index` |
| `density_value` | `density` |
| `moisture_pct` | `moisture_percent` |
| `contamination_pct` | `contamination_percent` |

### 6. Residue is derived intelligence, not profile schema

- Intake may keep a **computed** `has_residue` for UI and legacy packets.
- Material profile **must not** store `has_residue`.
- Matchers/normalizers use **derived** `has_residue` in bridge payloads via `profile_features.compute_has_residue_feature()` (see ADR-005).

Signals: contamination %, contamination notes, material attributes, source/process context, freeform notes.

### 7. Create / sync flow

```
Intake (draft) ──optional link──► Material Profile (facility + polymer + form)
       │                                    ▲
       │  _create_material_profile_from_intake()
       │  build_material_profile_vals_from_intake()
       └──────────────────────────────────────┘
```

On `material_profile_id` onchange, intake pre-fills snapshots from the profile (including mapped quality fields and supply/geo deltas).

## Consequences

### Positive

- Clear ownership for PRs and agent tasks (no “field soup” on profile).
- Stable CEG/Gate payloads can target canonical profile field names.
- Repeat suppliers reuse one profile per `(partner_id, polymer_id, form_id)` triple.

### Negative / constraints

- Two places to read material specs during an active deal (profile + intake snapshot); intake wins for instance-level edits until synced.
- Integrations must use ADR-005 mapping tables, not intake-only legacy keys (`polymer`, `form`, `estimated_lbs`).

## Compliance

1. New material dimensions use ADR-001 Many2one master data — not duplicate Selections on intake.
2. Do not add intake workflow fields to `plasticos.material.profile`.
3. Do not add `target_price` or stored `has_residue` to `plasticos.material.profile`.
4. Cross-layer offer/transaction links from intake use **Integer** FKs where required (existing layer-isolation rule).

## References

- `plasticos_intake/models/intake.py` — intake model and `_create_material_profile_from_intake`
- `plasticos_material_profile/models/material_profile.py` — canonical profile schema
- `plasticos_intake/README.md`, `plasticos_material_profile/README.md`
