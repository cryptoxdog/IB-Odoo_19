# Boolean Field Matrix — Buyer Matching Logic

**Last Updated:** 2026-02-23
**Module:** `plasticos_buyer_match_engine`
**Source Files:** `facility_profile.py`, `graph_service.py`, `matcher.py`

---

## Overview

This document defines how each Boolean field affects buyer matching logic.

**Key Concepts:**
- **HARD GATE** — Must match or buyer is excluded
- **SOFT SIGNAL** — Affects ranking score, not eligibility
- **CONDITIONAL GATE** — Only applies when intake has specific attribute
- **NULL Behavior** — What happens when field is not set

---

## IMPORTANT: `facility_role` vs `company_type`

These are **different fields** — don't confuse them:

| Field | Model | Purpose | Values |
|-------|-------|---------|--------|
| `company_type` | `res.partner` (Odoo core) | Person vs Company | `person`, `company` |
| `x_facility_role` | `res.partner` (Plasticos extension) | **Business role** | `processor`, `broker`, `manufacturer`, `mrf`, `compounder`, `recycler`, `distributor`, `carrier`, `other` |

**In Neo4j:** Synced as `facility_role` (from `partner.x_facility_role`)

**Source of truth:** `partner_type_id` → `plasticos.partner.type.code`

**Used in Cypher:** `f.facility_role = 'broker'` to exclude brokers from equipment gates (they resell, not process)

---

## HARD GATES (Exclusionary)

| Field | Location | Gate Logic | Notes |
|-------|----------|------------|-------|
| `polymer` | MaterialProfile | `m.polymer = $polymer` | Intake polymer must match buyer's accepted polymers |
| `process_type` | FacilityProfile | MFI-Process compatibility | Injection can't run blow mold grade; brokers excluded from process gates |

### Process Type × MFI Matrix

| Process Type | MFI Range | Rationale |
|--------------|-----------|-----------|
| `injection` | MI ≥ 1.0 | Material must flow through runners/gates |
| `blow_mold` | MI ≤ 2.0 | Parison must hold shape |
| `film_blown` | MI 0.5-2.5 | Bubble stability |
| `film_cast` | MI 0.5-2.5 | Sheet uniformity |
| `thermoform` | MI 1.0-8.0 | Sheet flow |
| `extrusion` | Any | Wide range acceptable |
| `compounding` | Any | Blending/modifying |
| `rotomold` | MI ≤ 5.0 | Powder sintering |

---

## EQUIPMENT FIELDS (Computed from `equipment_type_ids`)

| Field | NULL Meaning | Gate Type | Logic |
|-------|--------------|-----------|-------|
| `has_horizontal_baler` | No equipment entered | N/A | Supplier-side, not buyer matching |
| `has_downstroke_baler` | No equipment entered | N/A | Supplier-side, not buyer matching |
| `has_shredder` | No equipment entered | CONDITIONAL | Used in form-equipment gate; NULL = allow through |
| `has_granulator` | No equipment entered | CONDITIONAL | Used in form-equipment gate; NULL = allow through |
| `has_wash_line` | No equipment entered | SOFT | **NOT required for flake** (removed from gate) |
| `has_extruder` | No equipment entered | CONDITIONAL | Used for regrind/flake; NULL = allow through |
| `has_sorting_line` | No equipment entered | CONDITIONAL | **Required for PVC contamination gate** |

### Form × Equipment Gate (Implemented in `graph_service.py` lines 848-885)

**Brokers pass through all form-equipment gates** — they resell, not process.

| Intake Form | Cypher Logic | NULL Behavior |
|-------------|--------------|---------------|
| `bales` | `has_granulator = true OR has_shredder = true OR has_granulator IS NULL` | Allow through |
| `parts` | `has_granulator = true OR has_shredder = true OR has_granulator IS NULL` | Allow through |
| `regrind` | `has_extruder = true OR has_granulator = true OR handles_regrind = true OR has_extruder IS NULL` | Allow through |
| `flake` | `has_extruder = true OR handles_flake = true OR has_extruder IS NULL` | Allow through |
| `pellet` | `true` (no restriction) | N/A |
| `purge` | `has_granulator = true OR has_shredder = true OR has_granulator IS NULL` | Allow through |
| `lump` | `has_granulator = true OR has_shredder = true OR has_granulator IS NULL` | Allow through |
| `rollstock` | `true` (no restriction) | N/A |

**Key Changes from Previous Version:**
- ❌ Removed `has_wash_line` requirement for flake
- ❌ Removed equipment requirement for rollstock
- ✅ Added broker pass-through (`f.facility_role = 'broker'`)
- ✅ NULL equipment = allow through (incomplete profile, not "doesn't have")

---

## MATERIAL HANDLING FIELDS

**Source:** `facility_profile.py` lines 70-75 (pre-existing fields)
**Synced to Neo4j:** `handles_regrind`, `handles_flake`, `handles_rollstock` ✅

| Field | NULL Meaning | Gate Type | Cypher Usage |
|-------|--------------|-----------|--------------|
| `handles_bales` | Unknown | SOFT | Used as fallback in form gate |
| `handles_regrind` | Unknown | CONDITIONAL | `OR handles_regrind = true` in regrind gate |
| `handles_pellet` | Unknown | SOFT | Most equipment handles pellets |
| `handles_flake` | Unknown | CONDITIONAL | `OR handles_flake = true` in flake gate |
| `handles_rollstock` | Unknown | SOFT | No longer gated (removed) |

**Note:** These fields are **user-declared preferences**, not equipment-derived. Equipment fields (`has_granulator`, etc.) determine actual capability. Both are checked in form gates.

---

## QUALITY PROCESSING FIELDS

**Pattern:** `NOT $requires_X OR f.can_X`
**Synced to Neo4j:** `can_reduce_moisture` ✅

| Field | NULL Meaning | Gate Type | Cypher Logic |
|-------|--------------|-----------|--------------|
| `can_remove_metal` | Unknown → include | CONDITIONAL | `NOT $has_metal OR f.can_remove_metal` |
| `can_reduce_moisture` | Unknown → include | CONDITIONAL | `NOT $requires_drying OR f.can_reduce_moisture` |
| `can_filter_fr` | Unknown → include | CONDITIONAL | `NOT $has_fr OR f.can_filter_fr` |
| `can_screen_fines` | Unknown → include | SOFT | Not currently gated |

**Explanation:** If intake doesn't require the capability, buyer passes regardless. If intake requires it AND buyer has it, pass. If intake requires it AND buyer doesn't have it, exclude.

---

## CERTIFICATION FIELDS

**Pattern:** Pessimistic — must prove certification
**Synced to Neo4j:** `food_grade_certified`, `medical_grade_capable` ✅

| Field | NULL Meaning | Gate Type | Cypher Logic |
|-------|--------------|-----------|--------------|
| `iso_certified` | Unknown → exclude if required | CONDITIONAL | Future gate |
| `food_grade_certified` | Unknown → exclude if required | CONDITIONAL | `NOT $food_grade OR f.food_grade_certified = true` |
| `medical_grade_capable` | Unknown → exclude if required | CONDITIONAL | `NOT $medical_grade OR f.medical_grade_capable = true` |

**Explanation:** If intake requires food/medical grade AND buyer certification is NULL or False, exclude buyer. Buyer must **prove** certification to match certified material.

**Also used in PVC Contamination Gate:** Food/medical buyers excluded entirely when PVC detected.

---

## OPERATIONAL FIELDS

| Field | Current Default | NULL Meaning | Gate Type | Logic |
|-------|-----------------|--------------|-----------|-------|
| `accepts_spot` | ~~`default=True`~~ → REMOVE | Unknown → assume True | SOFT | Most facilities accept spot deals |
| `prefers_contract` | None | Unknown → no effect | SOFT | Scoring only |

**Action Required:** Remove `default=True` from `accepts_spot`. Matcher should assume True unless explicitly False.

---

## CONTAMINATION GATES (Material-side, Implemented)

**Source:** `graph_service.py` lines 888-920

### PVC Contamination Gate (lines 888-905)

**Applies when:** `$polymer IN ['hdpe', 'pp', 'HDPE', 'PP'] AND $has_pvc = true`

| Condition | Result |
|-----------|--------|
| `food_grade_certified = false` | Required (food buyers excluded) |
| `medical_grade_capable = false` | Required (medical buyers excluded) |
| `has_sorting_line = true` | **Required** (NIR or float-sink capability) |

**Cypher:**
```cypher
WHEN $polymer IN ['hdpe', 'pp', 'HDPE', 'PP'] AND $has_pvc = true
THEN (
  f.food_grade_certified = false
  AND f.medical_grade_capable = false
  AND f.has_sorting_line = true
)
```

### PP Contamination Gate (lines 907-920)

**Applies when:** `$polymer IN ['hdpe', 'HDPE'] AND $has_pp_contamination = true`

| Condition | Result |
|-----------|--------|
| `process_type = 'compounding'` | Required (compatibilizer capability) |

**Cypher:**
```cypher
WHEN $polymer IN ['hdpe', 'HDPE'] AND $has_pp_contamination = true
THEN f.process_type = 'compounding'
```

### Contamination Parameter Inference

| Param | Inferred From | In `_intake_to_match_params()` |
|-------|---------------|--------------------------------|
| `has_pvc` | `material_attribute_ids` contains `pvc_contaminated` | ✅ Implemented (line 625-629) |
| `has_pp_contamination` | `material_attribute_ids` contains `pp_contaminated` | ✅ Implemented (line 630-634) |
| `has_metal` | `material_attribute_ids` contains `with_metal` | ✅ Existing (line 613-618) |
| `has_fr` | `material_attribute_ids` contains `flame_retardant` | ✅ Existing (line 619-623) |

---

## APPLICATION CLASS (Selection)

**Source:** `facility_profile.py` — Selection field (not Char)

| Value | Label | Contamination Tolerance |
|-------|-------|------------------------|
| `food` | Food Contact | 0% (zero tolerance) |
| `medical` | Medical | 0% (zero tolerance) |
| `automotive` | Automotive | ≤ 0.5% |
| `packaging` | Packaging | ≤ 1% |
| `agricultural` | Agricultural | ≤ 1% |
| `construction` | Construction | ≤ 2% |

**Note:** Must be set manually or via AI enrichment. No automatic backfill from certifications (low value).

---

## FACILITY ROLE FIELD

**Source:** `facility_profile.py`
**Synced to Neo4j:** `facility_role` ✅

| Value | Gate Behavior |
|-------|---------------|
| `broker` | **Passes through all form-equipment gates** — brokers resell, not process |
| `processor` | Subject to all equipment gates |
| `compounder` | Subject to all equipment gates; implies `process_type = 'compounding'` |
| Other | Subject to all equipment gates |

---

## NULL Handling Summary

| Category | NULL Behavior | Rationale |
|----------|---------------|-----------|
| Equipment (computed) | NULL = allow through | Sales didn't enter data; incomplete profile ≠ "doesn't have" |
| Material Handling | NULL = allow through | User preference, use equipment as fallback |
| Quality Processing | NULL = include unless intake requires | Optimistic pattern |
| Certification | NULL = exclude if intake requires | Must prove certification |
| Operational | NULL = assume True (`accepts_spot`) | Most facilities accept |
| Contamination | N/A (material-side params) | Inferred from `material_attribute_ids` |

---

## Neo4j Sync Fields (Implemented)

**Added to `_build_facility_payloads` and `sync_facility_nodes`:**

| Field | Synced | Used In |
|-------|--------|---------|
| `facility_role` | ✅ | Broker pass-through |
| `has_shredder` | ✅ | Form-equipment gate |
| `has_granulator` | ✅ | Form-equipment gate |
| `has_wash_line` | ✅ | (soft signal only) |
| `has_extruder` | ✅ | Form-equipment gate |
| `has_sorting_line` | ✅ | PVC contamination gate |
| `handles_regrind` | ✅ | Form-equipment gate |
| `handles_flake` | ✅ | Form-equipment gate |
| `handles_rollstock` | ✅ | (soft signal only) |
| `food_grade_certified` | ✅ | Certification gate, PVC gate |
| `medical_grade_capable` | ✅ | Certification gate, PVC gate |
| `process_type` | ✅ | MFI-Process gate, PP gate |
| `can_reduce_moisture` | ✅ | Quality processing gate |

---

## Transaction Edge Sync (Implemented)

**Method:** `sync_transaction_edges()`

Creates `TRANSACTED_WITH` edges between Facility nodes:
- `tx_count`: Number of transactions
- `last_tx_date`: Most recent transaction date

Used for recency-weighted scoring in soft signals.

---

## Matcher Code Pattern

**Old (WRONG):**
```python
if getattr(facility, "has_granulator", False):  # Treats NULL as False
```

**New (CORRECT) — Implemented in `_derive_acceptable_forms()`:**
```python
# Get equipment values (None = unknown, True = has, False = doesn't have)
has_granulator = getattr(facility, "has_granulator", None)
has_shredder = getattr(facility, "has_shredder", None)

# True = explicitly has; None = unknown (allow through)
if has_granulator is True or has_shredder is True:
    forms.update([...])  # Has equipment
elif has_granulator is None and has_shredder is None:
    # NULL equipment = incomplete profile, allow ALL forms through
    forms.update([...])  # Graph Service does refined filtering
```

**Key Change:** NULL equipment no longer excludes buyers — incomplete profile ≠ "doesn't have".

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-02-23 | Initial matrix created | Cursor |
| 2026-02-23 | Corrected: equipment NULL means "not entered", not "doesn't have" | Igor |
| 2026-02-23 | Corrected: `has_extruder` is SOFT signal, not hard gate | Igor |
| 2026-02-23 | Corrected: `has_shredder` + `has_granulator` = EITHER works for bales | Igor |
| 2026-02-23 | Added: `has_sorting_line` required for PVC contamination gate | Igor |
| 2026-02-23 | Clarified: Material Handling fields are user-declared, pre-existing | Igor |
| 2026-02-23 | Implemented: Form-equipment gate with broker pass-through | Cursor |
| 2026-02-23 | Implemented: PVC contamination gate (food/medical exclusion + sorting_line) | Cursor |
| 2026-02-23 | Implemented: PP contamination gate (compounding required) | Cursor |
| 2026-02-23 | Implemented: Neo4j facility sync with equipment/certification fields | Cursor |
| 2026-02-23 | Implemented: Transaction edge sync for recency scoring | Cursor |
| 2026-02-23 | Removed: `has_wash_line` requirement for flake | Igor |
| 2026-02-23 | Removed: Equipment requirement for rollstock | Igor |

---

## TODO

- [x] Remove `default=True` from `accepts_spot` in `facility_profile.py` ✅ 2026-02-23
- [x] Update matcher.py to use correct NULL handling pattern ✅ 2026-02-23
- [x] Add `pvc_contaminated` and `pp_contaminated` to `material_attribute_data.xml` ✅ Already existed
- [x] Update `_intake_to_match_params()` to infer `has_pvc` and `has_pp_contamination` ✅ Already implemented
- [ ] Wire `application_class` to Neo4j sync
- [ ] Add `has_sorting_line` scoring boost for MIXED materials (soft signal)
