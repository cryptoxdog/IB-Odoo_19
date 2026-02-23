# 📊 GAP ANALYSIS: 45-Step Framework vs plasticos_buyer_match_engine

**Date:** 2026-02-23
**Reference:** `docs/02-25-2026/45_STEP_REASONING_FRAMEWORK.md`
**Module:** `plasticos_buyer_match_engine`

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Total Steps** | 45 |
| **Implemented** | ~22 (49%) |
| **Partial** | ~8 (18%) |
| **Gaps** | ~15 (33%) |

**Recent Progress (This Session):**
- ✅ PVC Contamination Gate (Step 10) — IMPLEMENTED
- ✅ PP Contamination Gate (Step 9) — IMPLEMENTED
- ✅ Form-Equipment Gate (Steps 40-41) — IMPLEMENTED
- ✅ MFI-Process Gate — IMPLEMENTED
- ✅ Transaction Edge Sync — IMPLEMENTED
- ✅ Broker Pass-Through — IMPLEMENTED

---

## Current vs Target

| Layer | Steps | Implemented | Gap | Status |
|-------|-------|-------------|-----|--------|
| 1. Material Characterization | 8 | 4 | 4 | 🟡 50% |
| 2. Contamination Analysis | 8 | 6 | 2 | 🟢 75% |
| 3. Color & Aesthetics | 5 | 1 | 4 | 🔴 20% |
| 4. Filler & Additive Science | 10 | 1 | 9 | 🔴 10% |
| 5. Application Targeting | 8 | 3 | 5 | 🟡 38% |
| 6. Processing & Equipment | 6 | 5 | 1 | 🟢 83% |
| 7-9. Geo/Economic/Strategic | 3 | 2 | 1 | 🟡 67% |
| **TOTAL** | **48** | **22** | **26** | **~46%** |

---

## Layer-by-Layer Status

### Layer 1: Material Characterization (Steps 1-8)

| Step | Description | Status | Implementation |
|------|-------------|--------|----------------|
| 1 | Polymer Type & Grade | ✅ DONE | `m.polymer = $polymer` |
| 2 | Melt Index Range | ✅ DONE | `f.melt_index_min/max` + MFI-Process gate |
| 3 | Density Window | ✅ DONE | `f.density_min/max` |
| 4 | HLMI/MI Ratio (MWD) | ❌ GAP | Not tracked |
| 5 | Recycling Generation | ✅ DONE | `source_type` (PCR/PIR) |
| 6 | Recycle Cycle Estimation | ❌ GAP | Not tracked |
| 7 | Property Degradation | ❌ GAP | Not tracked |
| 8 | Virgin Blend Requirement | ❌ GAP | Not tracked |

**Coverage: 4/8 = 50%**

---

### Layer 2: Contamination Analysis (Steps 9-16) 🟢 BEST COVERAGE

| Step | Description | Status | Implementation |
|------|-------------|--------|----------------|
| 9 | PP Cross-Polymer | ✅ **NEW** | `$has_pp_contamination` → require compounding |
| 10 | PVC Zero-Tolerance | ✅ **NEW** | `$has_pvc` → exclude food/medical, require sorting_line |
| 11 | Moisture Hard Gate | ✅ DONE | `f.moisture_tolerance_pct` + `requires_dryer` |
| 12 | Dirt & Foreign Matter | ✅ DONE | `f.contamination_tolerance_pct` + `requires_wash_line` |
| 13 | Label/Adhesive Residue | ⚠️ PARTIAL | Covered by wash_line |
| 14 | Oil/Chemical Residue | ❌ GAP | Not tracked |
| 15 | Metal Contamination | ✅ DONE | `NOT $has_metal OR f.can_remove_metal` |
| 16 | Wood/Paper/Cardboard | ❌ GAP | Not tracked separately |

**Coverage: 6/8 = 75%**

---

### Layer 3: Color & Aesthetics (Steps 17-21)

| Step | Description | Status | Implementation |
|------|-------------|--------|----------------|
| 17 | Natural Color Premium | ⚠️ PARTIAL | `color_match` soft signal |
| 18 | Mixed Color Downcycle | ❌ GAP | No routing logic |
| 19 | Black Material NIR | ❌ GAP | Not tracked |
| 20 | Color Consistency | ❌ GAP | Not tracked |
| 21 | FDA Color Additive | ❌ GAP | Not tracked |

**Coverage: 1/5 = 20%**

---

### Layer 4: Filler & Additive Science (Steps 22-31) 🔴 BIGGEST GAP

| Step | Description | Status | Implementation |
|------|-------------|--------|----------------|
| 22 | Talc Filler Detection | ❌ GAP | Not tracked |
| 23 | CaCO3 Detection | ❌ GAP | Not tracked |
| 24 | Glass Fiber Reinforcement | ❌ GAP | Not tracked |
| 25 | Filler Cost Equivalence | ❌ GAP | Not calculated |
| 26 | MAPE Compatibilizer | ⚠️ PARTIAL | PP gate requires compounding |
| 27 | UV Stabilizer Assessment | ❌ GAP | Not tracked |
| 28 | Antioxidant Depletion | ❌ GAP | Not tracked |
| 29 | Flame Retardant | ✅ DONE | `has_fr` + `can_filter_fr` |
| 30 | Odor/VOC Management | ❌ GAP | Not tracked |
| 31 | Melt Strength Enhancement | ❌ GAP | Not tracked |

**Coverage: 1/10 = 10%**

---

### Layer 5: Application Targeting (Steps 32-39)

| Step | Description | Status | Implementation |
|------|-------------|--------|----------------|
| 32 | Food Contact Gate | ✅ DONE | `NOT $food_grade OR f.food_grade_certified` |
| 33 | Medical Grade Gate | ✅ DONE | `NOT $medical_grade OR f.medical_grade_capable` |
| 34 | Pressure Pipe | ❌ GAP | Not tracked |
| 35 | Pallet & Structural | ⚠️ PARTIAL | `application_class` Selection added |
| 36 | Automotive Interior | ❌ GAP | Not tracked |
| 37 | Chemical Storage | ❌ GAP | Not tracked |
| 38 | Consumer Products | ❌ GAP | Not tracked |
| 39 | Industrial/Utility | ❌ GAP | Not tracked |

**Coverage: 3/8 = 38%**

---

### Layer 6: Processing & Equipment (Steps 40-45) 🟢 GOOD COVERAGE

| Step | Description | Status | Implementation |
|------|-------------|--------|----------------|
| 40 | Blow Molding Match | ✅ **NEW** | MFI-Process gate (MI ≤ 2.0) |
| 41 | Injection Incompatibility | ✅ **NEW** | MFI-Process gate (MI ≥ 1.0) |
| 42 | Washing Line | ✅ DONE | `NOT $requires_wash_line OR f.has_wash_line` |
| 43 | Drying Equipment | ✅ DONE | `NOT $requires_dryer OR f.can_reduce_moisture` |
| 44 | Compounding Capability | ✅ **NEW** | PP gate requires `process_type = 'compounding'` |
| 45 | QC Laboratory | ❌ GAP | Not tracked |

**Coverage: 5/6 = 83%**

---

### Layers 7-9: Geo, Economic, Strategic

| Layer | Description | Status | Implementation |
|-------|-------------|--------|----------------|
| 7 | Geographic & Logistics | ✅ DONE | `point.distance()` geo filter |
| 8 | Economic Viability | ⚠️ PARTIAL | Transaction history scoring |
| 9 | Strategic Positioning | ❌ GAP | No market positioning |

**Coverage: 2/3 = 67%**

---

## Gaps (Prioritized)

| # | Gap | Priority | Impact | Effort | Fix |
|---|-----|----------|--------|--------|-----|
| 1 | Filler Detection (talc/CaCO3/GF) | 🔴 HIGH | Changes buyer routing | MEDIUM | Add `filler_type`, `filler_pct` to material_profile |
| 2 | Property Degradation | 🔴 HIGH | Affects quality matching | MEDIUM | Add `recycle_cycles`, `property_retention_pct` |
| 3 | Oil/Chemical Residue | 🟠 MEDIUM | Safety concern | LOW | Add `has_oil_residue` attribute |
| 4 | Odor/VOC Management | 🟠 MEDIUM | Consumer products | LOW | Add `odor_level` Selection |
| 5 | Color Consistency | 🟡 LOW | Lot-to-lot variation | LOW | Add `color_consistency_required` |
| 6 | QC Lab Capability | 🟡 LOW | Food/Medical testing | LOW | Add `has_qc_lab` to facility |
| 7 | Application Routing | 🟡 LOW | Already have `application_class` | LOW | Wire to Cypher |
| 8 | Black NIR Challenge | 🟡 LOW | Sorting limitation | LOW | Add `is_black` flag |

---

## What's NOW Implemented (Complete List)

### Hard Gates (17 Total)

```
✅ 1.  Polymer match                    m.polymer = $polymer
✅ 2.  Accepted polymers                $polymer IN f.accepted_polymers
✅ 3.  Density range                    f.density_min/max
✅ 4.  MFI range                        f.melt_index_min/max
✅ 5.  Contamination tolerance          f.contamination_tolerance_pct
✅ 6.  Moisture tolerance               f.moisture_tolerance_pct
✅ 7.  Metal removal capability         NOT $has_metal OR f.can_remove_metal
✅ 8.  FR filtering capability          NOT $has_fr OR f.can_filter_fr
✅ 9.  Lot size range                   f.min/max_lot_size_lbs
✅ 10. Geo radius                       point.distance() <= radius
✅ 11. Wash line requirement            NOT $requires_wash_line OR f.has_wash_line
✅ 12. Dryer requirement                NOT $requires_dryer OR f.can_reduce_moisture
✅ 13. Food grade certification         NOT $food_grade OR f.food_grade_certified
✅ 14. Medical grade capability         NOT $medical_grade OR f.medical_grade_capable
✅ 15. MFI-Process compatibility        CASE f.process_type (injection/blow_mold/etc)
✅ 16. Form-Equipment compatibility     CASE $form (bales/regrind/flake/etc)
✅ 17. PVC contamination gate           Exclude food/medical, require sorting_line
✅ 18. PP contamination gate            Require compounding capability
```

### Soft Signals (9 Total)

```
✅ Form match                          40% of hard_score
✅ Source type match                   30% of hard_score
✅ Certification match                 30% of hard_score
✅ Color match                         25% of soft_score
✅ Packaging type match                5% of soft_score
✅ Origin form match                   10% of soft_score
✅ Process type match                  10% of soft_score
✅ Transaction history bonus           Logarithmic tx_count + recency decay
✅ Geo proximity score                 Linear decay with distance
```

### Special Logic

```
✅ Broker pass-through                 f.facility_role = 'broker' bypasses equipment gates
✅ NULL equipment handling             NULL = incomplete profile, allow through
✅ Transaction edge sync               TRANSACTED_WITH edges with tx_count, last_tx_date
```

---

## Effort Estimate

| Phase | Gaps Addressed | Effort |
|-------|----------------|--------|
| Phase 1: Filler Science | 4 gaps (Steps 22-25) | 2-3 days |
| Phase 2: Property Degradation | 3 gaps (Steps 6-8) | 1-2 days |
| Phase 3: Odor/VOC | 1 gap (Step 30) | 0.5 days |
| Phase 4: Application Routing | 5 gaps (Steps 34-39) | 2-3 days |
| Phase 5: Color Logic | 4 gaps (Steps 17-21) | 1-2 days |
| **TOTAL** | **17 gaps** | **7-11 days** |

---

## Recommended GMPs

| GMP | Scope | Gaps Addressed | Priority |
|-----|-------|----------------|----------|
| GMP-FILLER | Add filler_type/filler_pct to material_profile, route to pallet/structural | Steps 22-25 | 🔴 HIGH |
| GMP-DEGRADE | Add recycle_cycles, property_retention_pct, virgin_blend logic | Steps 6-8 | 🔴 HIGH |
| GMP-ODOR | Add odor_level Selection, exclude consumer products if high | Step 30 | 🟠 MEDIUM |
| GMP-APPCLASS | Wire application_class to Cypher, add routing logic | Steps 34-39 | 🟡 LOW |
| GMP-COLOR | Add color routing logic (natural premium, black NIR) | Steps 17-21 | 🟡 LOW |

---

## Conclusion

The `plasticos_buyer_match_engine` now implements **~49% of the 45-step framework** with strong coverage in:
- **Contamination Analysis** (75%) — PVC/PP gates now implemented
- **Processing & Equipment** (83%) — MFI-Process, Form-Equipment gates complete

The biggest gaps are in:
- **Filler & Additive Science** (10%) — Requires new data model fields
- **Color & Aesthetics** (20%) — Requires routing logic
- **Application Targeting** (38%) — `application_class` exists but not wired to Cypher

**The foundation is solid. The hard gates work. Remaining work is incremental data model expansion.**
