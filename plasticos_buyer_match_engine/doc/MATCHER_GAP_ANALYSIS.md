# Gap Analysis: Graph Service vs Capability Matcher

**Date:** 2026-02-23 (Updated)
**Module:** `plasticos_buyer_match_engine`
**Status:** ✅ TWO-STAGE ORCHESTRATOR IMPLEMENTED

---

## Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| Capability Matcher | ✅ Updated | `services/matcher.py` |
| Form Equipment Logic | ✅ Added | `matcher._can_handle_form()`, `matcher._derive_acceptable_forms()` |
| Two-Stage Orchestrator | ✅ Added | `graph_service.match_buyers_two_stage()` |
| Stage 2 Query | ✅ Added | `graph_service._build_stage2_query()` |
| Result Persistence | ✅ Added | `graph_service._persist_two_stage_results()` |

---

## Executive Summary

**Are they complementary?** YES — they run in SEQUENCE:

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Capability Matcher (FIRST)                             │
│ ─────────────────────────────────────                           │
│ • Python deterministic hard gates                               │
│ • Eliminates noise: polymer, form, source_type exact match      │
│ • Fast DB query on buyer.capability lanes                       │
│ • Result: Candidates that CAN physically accept the material    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Graph Service (SECOND)                                 │
│ ─────────────────────────────────────                           │
│ • Neo4j refined analysis on survivors                           │
│ • Range-based gates: MFI, density, contamination tolerance      │
│ • Soft signals: color, packaging, transaction history           │
│ • Weighted scoring for ranking                                  │
│ • Result: Best matches with scores                              │
└─────────────────────────────────────────────────────────────────┘
```

| Aspect | Capability Matcher (Stage 1) | Graph Service (Stage 2) |
|--------|------------------------------|-------------------------|
| **Purpose** | Eliminate incompatible | Rank compatible |
| **Gate Type** | Deterministic (exact match) | Range-based + soft signals |
| **Data Source** | Odoo `buyer.capability` lanes | Neo4j graph |
| **Speed** | Fast (indexed DB query) | Fast (graph traversal) |
| **Output** | Pass/Fail per lane | Scored ranked list |

**Key Insight:** Capability Matcher doesn't check MFI because that's a RANGE, not deterministic. It checks polymer/form/source_type which are EXACT matches.

---

## Side-by-Side Gate Comparison

### Identity Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Polymer match | ✅ `m.polymer = $polymer` | ✅ `polymer = material.polymer` | TIE |
| Form match | ⚠️ Soft signal only | ✅ Hard gate | **Matcher** |
| Source type match | ⚠️ Soft signal only | ✅ Hard gate | **Matcher** |
| Accepted polymers | ✅ `$polymer IN f.accepted_polymers` | ❌ Not implemented | **Graph** |

**Gap:** Graph treats form/source_type as soft signals; Matcher treats them as hard gates.

---

### Material Property Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Density range | ✅ `f.density_min/max` | ❌ Not implemented | **Graph** |
| MFI range | ✅ `f.melt_index_min/max` | ❌ Not implemented | **Graph** |
| Contamination | ✅ `f.contamination_tolerance_pct` | ✅ `cap.max_contamination_pct` | TIE |
| Moisture | ✅ `f.moisture_tolerance_pct` | ✅ `cap.max_moisture_pct` | TIE |

**Gap:** Matcher lacks density/MFI gates.

---

### Contamination Capability Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Metal removal | ✅ `NOT $has_metal OR f.can_remove_metal` | ❌ Not implemented | **Graph** |
| FR filtering | ✅ `NOT $has_fr OR f.can_filter_fr` | ❌ Not implemented | **Graph** |
| PVC tolerance | ❌ Not implemented | ❌ Not implemented | **BOTH GAP** |

**Gap:** Neither handles PVC zero-tolerance gate.

---

### Volume/Capacity Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Min lot size | ✅ `f.min_lot_size_lbs` | ✅ `cap.min_volume_lbs` | TIE |
| Max lot size | ✅ `f.max_lot_size_lbs` | ✅ `cap.max_volume_lbs` | TIE |
| Monthly throughput | ❌ Not implemented | ❌ Not implemented | **BOTH GAP** |

---

### Equipment Capability Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Wash line | ✅ `NOT $requires_wash_line OR f.has_wash_line` | ❌ Not implemented | **Graph** |
| Dryer | ✅ `NOT $requires_dryer OR f.can_reduce_moisture` | ❌ Not implemented | **Graph** |
| Compounder | ❌ Synced but not gated | ❌ Not implemented | **BOTH GAP** |
| Form handling (baler, granulator) | ❌ Synced but not gated | ❌ Not implemented | **BOTH GAP** |

---

### Certification Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Food grade | ✅ `NOT $food_grade OR f.food_grade_certified` | ✅ `cap.requires_food_grade` | TIE |
| Medical grade | ✅ `NOT $medical_grade OR f.medical_grade_capable` | ✅ `cap.requires_medical_grade` | TIE |
| ISO certified | ❌ Synced but not gated | ❌ Not implemented | **BOTH GAP** |
| SQF certified | ❌ Synced but not gated | ❌ Not implemented | **BOTH GAP** |

---

### Geographic Gates

| Gate | Graph Service | Capability Matcher | Winner |
|------|---------------|-------------------|--------|
| Distance filter | ✅ `point.distance() <= $radius_meters` | ✅ Haversine calculation | TIE |
| Per-buyer radius | ❌ Global radius only | ✅ `cap.radius_miles` per lane | **Matcher** |

**Gap:** Graph uses global radius; Matcher allows per-capability radius.

---

### Scoring & Ranking

| Feature | Graph Service | Capability Matcher | Winner |
|---------|---------------|-------------------|--------|
| Weighted scoring | ✅ 4 weights (hard/soft/geo/tx) | ❌ Distance only | **Graph** |
| Transaction history | ✅ `tx_count` bonus | ❌ Not implemented | **Graph** |
| Color match | ✅ Soft signal | ❌ Not implemented | **Graph** |
| Process type match | ✅ Soft signal | ✅ Stored but not scored | **Graph** |

---

## Summary Scorecard

| Category | Graph Service | Capability Matcher |
|----------|---------------|-------------------|
| Identity gates | 2/4 | 3/4 |
| Property gates | 4/4 | 2/4 |
| Contamination gates | 2/3 | 0/3 |
| Volume gates | 2/3 | 2/3 |
| Equipment gates | 2/4 | 0/4 |
| Certification gates | 2/4 | 2/4 |
| Geo gates | 1/2 | 2/2 |
| Scoring | 4/4 | 1/4 |
| **TOTAL** | **19/28 (68%)** | **12/28 (43%)** |

---

## Remaining Gates to Add (Combined)

### HIGH PRIORITY — Not in Either System

| Gate | 45-Step Reference | Implementation |
|------|-------------------|----------------|
| **PVC Zero-Tolerance** | Step 10 | `AND (NOT $has_pvc OR f.pvc_tolerant = true)` |
| **Form Handling** | Step 40-41 | `AND ($form = 'bales' → f.has_baler)` |
| **Compatibilizer Capability** | Step 44 | `AND (NOT $requires_compatibilizer OR f.has_extruder)` — compounders have extruders |
| **Monthly Throughput** | Layer 6 | `AND (f.max_monthly_throughput_lbs >= $lot_size_lbs)` |

### MEDIUM PRIORITY — In Graph, Not Matcher

| Gate | Graph Has | Add to Matcher |
|------|-----------|----------------|
| Density range | ✅ | Add `min_density`, `max_density` to capability |
| MFI range | ✅ | Add `min_mfi`, `max_mfi` to capability |
| Metal removal | ✅ | Add `requires_metal_removal` to capability |
| FR filtering | ✅ | Add `requires_fr_filtering` to capability |
| Wash line | ✅ | Add `requires_wash_line` to capability |
| Dryer | ✅ | Add `requires_dryer` to capability |

### MEDIUM PRIORITY — In Matcher, Not Graph

| Gate | Matcher Has | Add to Graph |
|------|-------------|--------------|
| Form as hard gate | ✅ | Convert from soft signal to hard gate |
| Source type as hard gate | ✅ | Convert from soft signal to hard gate |
| Per-buyer radius | ✅ | Add `f.max_radius_miles` to Facility node |

### LOWER PRIORITY — 45-Step Framework Gaps

| Gate | 45-Step Reference | Notes |
|------|-------------------|-------|
| Filler detection (talc, CaCO3, GF) | Steps 22-24 | Requires new fields |
| Property degradation | Steps 6-7 | Requires recycle_cycles field |
| Color hard gates | Steps 17-21 | Natural vs mixed routing |
| Application class routing | Steps 32-39 | Pallet vs food vs automotive |
| QC lab capability | Step 45 | For food/medical |

---

## Complementary Usage Pattern

### Correct Execution Order

```
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 1: Capability Matcher (Deterministic Hard Gates)          │
│ ─────────────────────────────────────────────────────           │
│ • Query buyer.capability lanes by exact match:                  │
│   - polymer = intake.polymer                                    │
│   - form = intake.form (or equipment-derived)                   │
│   - source_type = intake.source_type                            │
│ • Apply quality gates: contamination, moisture                  │
│ • Apply volume gates: min/max lot size                          │
│ • Apply geo gate: per-buyer radius_miles                        │
│ • Result: Facility IDs that CAN accept this material            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGE 2: Graph Service (Range Gates + Scoring)                  │
│ ─────────────────────────────────────────────────               │
│ • Filter to Stage 1 survivors only                              │
│ • Apply range-based gates:                                      │
│   - MFI range (melt_index_min/max)                              │
│   - Density range (density_min/max)                             │
│   - Equipment capability (wash_line, dryer, etc.)               │
│ • Apply soft signals for scoring:                               │
│   - Color match, packaging match                                │
│   - Transaction history bonus                                   │
│   - Geo proximity score                                         │
│ • Result: Ranked list with composite scores                     │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# In graph_service.py or new hybrid_matcher.py:

def match_buyers_hybrid(self, intake):
    """Two-stage matching: Graph discovery → Capability validation."""

    # Stage 1: Graph-based discovery (broad, fast)
    graph_results = self.match_buyers_for_intake(intake)
    if not graph_results:
        return []

    # Extract facility IDs from graph results
    facility_ids = [r.get("facility_partner_id") for r in graph_results]

    # Stage 2: Capability-based validation (precise, slower)
    from ..services.matcher import PlasticosMatcher
    matcher = PlasticosMatcher(self.env)

    # Filter capabilities to only graph-matched facilities
    material = intake.material_profile_id
    domain = [
        ("active", "=", True),
        ("facility_id.partner_id", "in", facility_ids),
        ("source_type", "=", material.source_type),
        ("polymer", "=", material.polymer),
        ("form", "=", material.form),
    ]
    capabilities = self.env["plasticos.buyer.capability"].search(domain)

    # Evaluate each capability
    validated = []
    for cap in capabilities:
        result = matcher._evaluate(cap, material, intake)
        if result["eligible"]:
            # Merge with graph score
            graph_match = next(
                (r for r in graph_results
                 if r.get("facility_partner_id") == cap.facility_id.partner_id.id),
                None
            )
            if graph_match:
                result["graph_score"] = graph_match.get("score", 0)
                result["combined_score"] = (
                    result["graph_score"] * 0.6 +
                    (100 - result["distance_miles"]) * 0.4
                )
                validated.append(result)

    # Sort by combined score
    validated.sort(key=lambda x: x.get("combined_score", 0), reverse=True)

    return validated
```

---

## Form Handling Equipment Logic

**Key Insight:** A buyer's ability to accept a form depends on their EQUIPMENT, not just their preference.

### Equipment → Form Capability Matrix

| Equipment | Can Accept | Notes |
|-----------|------------|-------|
| `has_granulator` OR `has_shredder` | bales, parts, lumps, rollstock, sheet | Size reduction → regrind |
| `has_extruder` | regrind, flake, pellet | Melt processing (pelletizing) |
| `has_wash_line` | any form | Adds cleaning capability |
| `has_horizontal_baler` OR `has_downstroke_baler` | bales | For re-baling |

**Note:** "Compounder" is a **company type** (they blend additives), not equipment. Compounders have extruders.

### Form Derivation Logic (for Capability Matcher)

```python
def _derive_acceptable_forms(self, facility_profile):
    """Derive forms a facility can accept based on equipment."""
    forms = set()

    # Granulator/shredder = can break down ANY form to regrind
    if facility_profile.has_granulator or facility_profile.has_shredder:
        forms.update(["bales", "parts", "lump", "rollstock", "sheet",
                      "regrind", "flake", "pellet", "purge"])

    # Extruder = regrind/flake → pellet
    elif facility_profile.has_extruder:
        forms.update(["regrind", "flake", "pellet"])

    # Always can handle what they explicitly declared
    if facility_profile.handles_bales:
        forms.add("bales")
    # ... etc

    return forms
```

---

## Equipment vs Company Type

### Critical Distinction

| Concept | Field | Meaning |
|---------|-------|---------|
| **Equipment** | `has_extruder` | Physical machine that melts/extrudes plastic |
| **Company Type** | `process_type = 'compounding'` | Business function (they blend additives) |

**Key Insight:** "Compounder" is a COMPANY TYPE, not equipment. Compounder companies have EXTRUDERS.

### Equipment Fields (Use These)

| Field | Meaning | Form Capability |
|-------|---------|-----------------|
| `has_granulator` | Size reduction machine | bales/parts → regrind |
| `has_shredder` | Size reduction machine | bales/parts → regrind |
| `has_extruder` | Melt processing machine | regrind/flake → pellet |
| `has_wash_line` | Cleaning equipment | Adds cleaning capability |

### Removed Fields (Pre-Production Cleanup)

| Field | Reason Removed |
|-------|----------------|
| `has_compounder` | "Compounder" is a company type, not equipment — use `has_extruder` |
| `has_pelletizer` | Duplicate of `has_extruder` |

### Not Relevant to Buyer Matching

| Field | Purpose | Why Not Matching |
|-------|---------|------------------|
| `max_monthly_throughput_lbs` | Capacity planning | Logistics, not material compatibility |
| `avg_truckload_lbs` | Logistics | Shipping, not material compatibility |

---

## Remaining Implementation Tasks

### HIGH PRIORITY — Wire Capability Matcher

1. **Create orchestrator method** in `graph_service.py`:
   ```python
   def match_buyers_two_stage(self, intake):
       """Stage 1: Capability Matcher → Stage 2: Graph Service."""
       # Stage 1: Deterministic hard gates
       matcher = PlasticosMatcher(self.env)
       candidates = matcher.match(intake)
       if not candidates:
           return []

       # Stage 2: Graph refinement on survivors
       facility_ids = [c["facility_id"] for c in candidates]
       return self.match_buyers_for_intake(intake, facility_ids=facility_ids)
   ```

2. **Add form equipment logic** to Capability Matcher
3. **Add PVC gate** to both systems

### MEDIUM PRIORITY — Enhance buyer.capability

Add fields for range-based gates (currently only in Graph):
- `min_density`, `max_density`
- `min_mfi`, `max_mfi`
- `pvc_tolerant`

### LOW PRIORITY — Not Relevant to Matching

These fields exist but are for capacity planning, not buyer matching:
- `max_monthly_throughput_lbs`
- `avg_truckload_lbs`

---

## Conclusion

| Question | Answer |
|----------|--------|
| Are they complementary? | **YES** — Matcher first (deterministic), Graph second (refined) |
| Should we merge them? | **NO** — Different purposes, different data sources |
| What's the correct order? | **Capability Matcher → Graph Service** |
| Why doesn't Matcher check MFI? | MFI is a RANGE, not deterministic. Graph handles ranges. |
| What's missing? | Form equipment logic, PVC gate, two-stage orchestrator |

The Capability Matcher eliminates noise with exact-match gates. The Graph Service refines survivors with range-based analysis and scoring.
