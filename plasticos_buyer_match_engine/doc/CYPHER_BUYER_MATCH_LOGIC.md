# Cypher Buyer Match Logic — Final Implementation

**Last Updated:** 2026-02-23
**Source:** `graph_service.py` → `match_buyers_for_intake()`
**Framework:** 45-Step Comprehensive Reasoning Framework (Mack 7.1)

---

## Summary of Custom Logic (Igor's Corrections)

| Topic | Original Proposal | Igor's Correction | Final Implementation |
|-------|-------------------|-------------------|----------------------|
| **Polymer Gate Redundancy** | Gate 1 (polymer on MaterialProfile) + Gate 2 (accepted_polymers) | "Same thing twice under different name!" | Removed Gate 2 — MaterialProfile already represents what facility accepts |
| **Bales/Parts Gate** | Hard require granulator/shredder | Brokers excluded from gate; NULL = allow | `facility_role = 'broker'` bypasses; `IS NULL` passes |
| **Flake Gate** | Required extruder OR wash_line | Wash line NOT required for flake | Removed `has_wash_line` from flake check |
| **Rollstock Gate** | Required handles_rollstock OR shredder | No equipment requirement | Removed entirely — `WHEN 'rollstock' THEN true` |
| **Purge/Lump Gate** | Required granulator | Yes, correct | Kept as-is |
| **Wash Line Threshold** | Dirt > 1% requires wash line | "Too aggressive" — use 5% | Changed to `dirt_pct > 5.0` |
| **PVC Gate** | Exclude food/medical only | Per 45-step: ALSO require sorting capability | Added `AND f.has_sorting_line = true` |
| **PP Contamination Gate** | Require compounding for HDPE with PP | "Companies can blend HDPE and PP without compounding!" | **REMOVED** — HDPE/PP blends are common |
| **`has_pvc`** | Standalone field | Infer from `material_attribute_ids` | Inferred from `pvc_contaminated` attribute code |
| **Transaction Scoring** | Flat tx_count bonus | Recency-weighted | `recency_factor` decays from 1.0 to 0.5 over 365 days |

---

## HARD GATES (Binary Exclusions)

### Gate 1: Polymer Match
```cypher
// Intake polymer must match buyer's MaterialProfile
// NOTE: This is the ONLY polymer gate needed. The MaterialProfile
// already represents what the facility accepts.
AND m.polymer = $polymer
```

### Gate 3-4: Density & MFI Range
```cypher
// Buyer's tolerance range must include intake values
AND (f.density_min IS NULL OR $density IS NULL OR f.density_min <= $density)
AND (f.density_max IS NULL OR $density IS NULL OR f.density_max >= $density)
AND (f.melt_index_min IS NULL OR $mfi IS NULL OR f.melt_index_min <= $mfi)
AND (f.melt_index_max IS NULL OR $mfi IS NULL OR f.melt_index_max >= $mfi)
```

### Gate 5-6: Contamination & Moisture Tolerance
```cypher
AND (f.contamination_tolerance_pct IS NULL OR f.contamination_tolerance_pct >= $contamination_pct)
AND (f.moisture_tolerance_pct IS NULL OR f.moisture_tolerance_pct >= $moisture_pct)
```

### Gate 7-8: Metal & FR Handling
```cypher
// If intake has metal, buyer must have removal capability
AND (NOT $has_metal OR f.can_remove_metal = true)
AND (NOT $has_fr OR f.can_filter_fr = true)
```

### Gate 9: Lot Size
```cypher
AND (f.min_lot_size_lbs IS NULL OR $lot_size_lbs = 0 OR f.min_lot_size_lbs <= $lot_size_lbs)
AND (f.max_lot_size_lbs IS NULL OR $lot_size_lbs = 0 OR f.max_lot_size_lbs >= $lot_size_lbs)
```

### Gate 10: Geo Radius
```cypher
WHERE CASE
  WHEN $intake_point IS NOT NULL AND f.location IS NOT NULL
  THEN point.distance(f.location, point($intake_point)) <= $radius_meters
  ELSE true
END
```

---

## EQUIPMENT CAPABILITY GATES

### Wash Line (Dirt > 5%)
```cypher
// Per Igor: dirt > 5% requires washing line (1% was too aggressive)
AND (NOT $requires_wash_line OR f.has_wash_line = true)
```

### Dryer (Moisture > 500 ppm)
```cypher
// Per 45-step Step 11: moisture > 500 ppm requires dryer
AND (NOT $requires_dryer OR f.can_reduce_moisture = true)
```

---

## MFI-PROCESS COMPATIBILITY GATE

```cypher
AND CASE f.process_type
  // Injection molding needs MI >= 1.0 for adequate flow length
  WHEN 'injection' THEN ($mfi IS NULL OR $mfi >= 1.0)
  // Blow molding needs MI <= 2.0 for parison integrity
  WHEN 'blow_mold' THEN ($mfi IS NULL OR $mfi <= 2.0)
  // Film blown/cast needs MI 0.5-2.5 for bubble stability
  WHEN 'film_blown' THEN ($mfi IS NULL OR ($mfi >= 0.5 AND $mfi <= 2.5))
  WHEN 'film_cast' THEN ($mfi IS NULL OR ($mfi >= 0.5 AND $mfi <= 2.5))
  // Thermoforming needs MI 1.0-8.0 for sheet flow
  WHEN 'thermoform' THEN ($mfi IS NULL OR ($mfi >= 1.0 AND $mfi <= 8.0))
  // Extrusion handles wide range
  WHEN 'extrusion' THEN true
  // Compounding handles everything
  WHEN 'compounding' THEN true
  // Rotomolding needs very low MI
  WHEN 'rotomold' THEN ($mfi IS NULL OR $mfi <= 5.0)
  ELSE true
END
```

---

## FORM-EQUIPMENT COMPATIBILITY GATE

**Key Correction:** Brokers pass through entirely (they resell, not process). NULL equipment = allow through.

```cypher
AND CASE
  // BROKERS BYPASS — they resell, facility profile may be blank
  WHEN f.facility_role = 'broker' THEN true
  ELSE CASE $form
    // Bales: granulator OR shredder (NULL = allow)
    WHEN 'bales' THEN (f.has_granulator = true OR f.has_shredder = true
                       OR f.has_granulator IS NULL)
    // Parts: granulator OR shredder (NULL = allow)
    WHEN 'parts' THEN (f.has_granulator = true OR f.has_shredder = true
                       OR f.has_granulator IS NULL)
    // Regrind: extruder OR granulator OR handles_regrind (NULL = allow)
    WHEN 'regrind' THEN (f.has_extruder = true
                         OR f.has_granulator = true
                         OR f.handles_regrind = true
                         OR f.has_extruder IS NULL)
    // Flake: extruder OR handles_flake (NO wash_line requirement!)
    WHEN 'flake' THEN (f.has_extruder = true
                       OR f.handles_flake = true
                       OR f.has_extruder IS NULL)
    // Pellet: no restriction
    WHEN 'pellet' THEN true
    // Purge/Lump: granulator OR shredder (NULL = allow)
    WHEN 'purge' THEN (f.has_granulator = true OR f.has_shredder = true
                       OR f.has_granulator IS NULL)
    WHEN 'lump' THEN (f.has_granulator = true OR f.has_shredder = true
                      OR f.has_granulator IS NULL)
    // Rollstock: NO equipment requirement (removed per Igor)
    WHEN 'rollstock' THEN true
    ELSE true
  END
END
```

---

## PVC CONTAMINATION GATE (HDPE/PP Only)

**Per 45-Step Framework Step 10:**
- PVC decomposes at HDPE/PP processing temps (200°C+), releasing HCl
- ZERO tolerance for food/medical applications
- REQUIRE PVC sorting capability (NIR or float-sink)

```cypher
AND CASE
  WHEN $polymer IN ['hdpe', 'pp', 'HDPE', 'PP'] AND $has_pvc = true
  THEN (
    // Exclude food/medical entirely
    f.food_grade_certified = false
    AND f.medical_grade_capable = false
    // AND require sorting capability
    AND f.has_sorting_line = true
  )
  ELSE true
END
```

**Inference in Python (`_intake_to_match_params`):**
```python
has_pvc = bool(
    getattr(mat, "has_pvc", False)
    or getattr(intake, "has_pvc", False)
    or "pvc_contaminated" in attr_codes  # Inferred from material_attribute_ids
)
```

---

## PP CONTAMINATION GATE — REMOVED

**Igor's Correction:** "Companies can blend HDPE and PP to make a product without compounding!"

This gate was **removed** because HDPE/PP blends are common in the industry and don't require specialized compounding capability.

---

## CERTIFICATION GATES

```cypher
// Food grade required → buyer must be certified
AND (NOT $food_grade OR f.food_grade_certified = true)

// Medical grade required → buyer must be capable
AND (NOT $medical_grade OR f.medical_grade_capable = true)
```

---

## SOFT SIGNALS (Scoring Factors)

| Signal | Weight | Logic |
|--------|--------|-------|
| Form match | 40% of hard_score | `m.form = $form` |
| Source type match | 30% of hard_score | `m.source_type = $source_type` |
| Certification match | 30% of hard_score | Food grade alignment |
| Color match | 25% of soft_score | `m.color = $color` |
| Origin form match | 10% of soft_score | `m.origin_form = $origin_form` |
| Process type match | 10% of soft_score | `f.process_type = $origin_process_type` |
| Packaging match | 5% of soft_score | `m.packaging_type = $packaging_type` |

---

## TRANSACTION HISTORY WITH RECENCY WEIGHTING

```cypher
OPTIONAL MATCH (supplier:Facility {facility_id: $supplier_facility_id})
               -[tx:TRANSACTED_WITH]->(f)

// Recency factor: 1.0 for today, decays to 0.5 at 365 days old
CASE
  WHEN tx.last_tx_date IS NOT NULL
  THEN 0.5 + 0.5 * (1.0 - toFloat(
    duration.inDays(date(tx.last_tx_date), date()).days
  ) / 365.0)
  ELSE 0.0
END AS recency_factor
```

**Transaction edge sync:** `sync_transaction_edges()` aggregates `plasticos.transaction` records by supplier-buyer pair, storing `tx_count` and `last_tx_date`.

---

## COMPOSITE SCORE CALCULATION

```cypher
// Final weighted score
($w1 * hard_score           // Default: 0.50
 + $w2 * soft_score         // Default: 0.15
 + $w3 * geo_score          // Default: 0.25
 + $w4 * tx_bonus           // Default: 0.10
) AS score

// Where tx_bonus = log(1 + tx_count) / log(101) * recency_factor
```

---

## NEO4J FACILITY NODE PROPERTIES (Synced)

| Property | Source | Used In |
|----------|--------|---------|
| `facility_role` | `partner.x_facility_role` | Form-equipment gate (broker bypass) |
| `process_type` | `facility_profile.process_type` | MFI-process gate |
| `has_shredder` | `facility_profile.has_shredder` | Form-equipment gate |
| `has_granulator` | `facility_profile.has_granulator` | Form-equipment gate |
| `has_extruder` | `facility_profile.has_extruder` | Form-equipment gate |
| `has_wash_line` | `facility_profile.has_wash_line` | Dirt gate |
| `has_sorting_line` | `facility_profile.has_sorting_line` | PVC gate |
| `handles_regrind` | `facility_profile.handles_regrind` | Form-equipment gate |
| `handles_flake` | `facility_profile.handles_flake` | Form-equipment gate |
| `can_reduce_moisture` | `facility_profile.can_reduce_moisture` | Moisture gate |
| `food_grade_certified` | `facility_profile.food_grade_certified` | PVC gate, cert gate |
| `medical_grade_capable` | `facility_profile.medical_grade_capable` | PVC gate, cert gate |

---

## DEPLOYMENT CHECKLIST

```bash
# 1. Update Odoo modules
odoo -u plasticos_material_profile,plasticos_facility_profile,plasticos_buyer_match_engine

# 2. Full Neo4j sync (includes facilities, materials, transactions)
env['plasticos.graph.service'].browse(1).sync_all(trigger='deploy')
```

---

## CHANGELOG

| Date | Change | Author |
|------|--------|--------|
| 2026-02-23 | Initial implementation of 45-step framework gates | Cursor |
| 2026-02-23 | Broker bypass for form-equipment gate | Igor |
| 2026-02-23 | Removed wash_line requirement for flake | Igor |
| 2026-02-23 | Removed equipment requirement for rollstock | Igor |
| 2026-02-23 | Added sorting_line requirement for PVC gate | Igor (per 45-step) |
| 2026-02-23 | Implemented recency-weighted transaction scoring | Cursor |
| 2026-02-23 | Added transaction edge sync (`sync_transaction_edges`) | Cursor |
| 2026-02-23 | Full facility property sync to Neo4j | Cursor |
| 2026-02-23 | Removed redundant accepted_polymers gate (MaterialProfile is sufficient) | Igor |
| 2026-02-23 | Changed wash line threshold from 1% to 5% | Igor |
| 2026-02-23 | Removed PP contamination gate (HDPE/PP blends are common) | Igor |
