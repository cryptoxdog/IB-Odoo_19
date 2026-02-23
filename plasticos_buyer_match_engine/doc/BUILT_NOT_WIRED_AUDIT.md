# Built But Not Wired — Audit Report

**Date:** 2026-02-23 (Updated)
**Module:** `plasticos_buyer_match_engine`
**Status:** ✅ TWO-STAGE PIPELINE IMPLEMENTED

---

## Executive Summary

| Engine | Location | Status | Coverage |
|--------|----------|--------|----------|
| **Graph Service** | `models/graph_service.py` | ✅ WIRED | 14 hard gates + scoring |
| **Capability Matcher** | `services/matcher.py` | ✅ WIRED (Stage 1) | 6 gates + form equipment logic |
| **Two-Stage Orchestrator** | `models/graph_service.py` | ✅ NEW | Combines both engines |
| **Mack Agent** | `Mack_agent_buyer_matching v7.0.py` | ⏸️ OUT OF SCOPE | External API — Odoo native first |

### What Changed (2026-02-23)

1. **Capability Matcher now runs as Stage 1** — eliminates noise with deterministic hard gates
2. **Form Equipment Logic added** — `_can_handle_form()` and `_derive_acceptable_forms()` check equipment capability
3. **Two-Stage Orchestrator** — `match_buyers_two_stage()` runs Matcher → Graph in sequence
4. **Stage 2 Query** — `_build_stage2_query()` filters to Stage 1 survivors only

### Entry Points

| Method | Purpose |
|--------|---------|
| `graph_service.match_buyers_for_intake(intake)` | Graph-only matching (original) |
| `graph_service.match_buyers_two_stage(intake)` | **NEW: Two-stage pipeline** |
| `matcher.match(intake)` | Capability Matcher standalone |

---

## 1. Capability Matcher — NOT WIRED

### What It Does

`services/matcher.py` implements a **deterministic Python-side matcher** using `plasticos.buyer.capability` records:

```python
class PlasticosMatcher:
    def match(self, intake):
        # Stage 1: Identity filter (DB query)
        domain = [
            ("source_type", "=", material.source_type),
            ("polymer", "=", material.polymer),
            ("form", "=", material.form),
        ]
        capabilities = self.env["plasticos.buyer.capability"].search(domain)

        # Stage 2: Gate evaluation (Python)
        for cap in capabilities:
            result = self._evaluate(cap, material, intake)
```

### Gates Implemented

| Gate | Field | Logic |
|------|-------|-------|
| Identity | source_type, polymer, form | Exact match |
| Contamination | max_contamination_pct | `material.contamination_percent <= cap.max_contamination_pct` |
| Moisture | max_moisture_pct | `material.moisture_percent <= cap.max_moisture_pct` |
| Volume Min | min_volume_lbs | `intake.quantity_per_load_lbs >= cap.min_volume_lbs` |
| Volume Max | max_volume_lbs | `intake.quantity_per_load_lbs <= cap.max_volume_lbs` |
| Food Grade | requires_food_grade | `material.food_grade = True` |
| Medical Grade | requires_medical_grade | `material.medical_grade = True` |
| Geo Radius | radius_miles | Haversine distance calculation |

### Why It's Not Wired

- No `match_buyers()` method calls `PlasticosMatcher.match()`
- The `plasticos.buyer.capability` model exists but isn't populated
- Graph service bypasses this entirely

### How to Wire

```python
# In graph_service.py or intake_extension.py:
from ..services.matcher import PlasticosMatcher

def match_buyers_hybrid(self, intake):
    """Hybrid matching: Graph + Capability lanes."""
    # 1. Graph-based matching (broad)
    graph_results = self.match_buyers_for_intake(intake)

    # 2. Capability-based filtering (precise)
    matcher = PlasticosMatcher(self.env)
    capability_results = matcher.match(intake)

    # 3. Merge results (intersection or union)
    return self._merge_match_results(graph_results, capability_results)
```

---

## 2. Buyer Capability Model — PENDING ODOO INSTALL

> **Note:** No data yet because Odoo isn't fully installed. Once running, populate via UI or import.

### What It Does

`models/buyer_capability.py` defines **capability lanes** — specific material combinations a buyer can accept:

```python
class PlasticosBuyerCapability(models.Model):
    _name = "plasticos.buyer.capability"

    facility_id = fields.Many2one("plasticos.facility.profile")
    source_type_id = fields.Many2one("plasticos.source.type")
    polymer_id = fields.Many2one("plasticos.polymer")
    form_id = fields.Many2one("plasticos.material.form")
    process_type = fields.Selection([...])

    # Quality gates
    max_contamination_pct = fields.Float()
    max_moisture_pct = fields.Float()

    # Volume gates
    min_volume_lbs = fields.Float()
    max_volume_lbs = fields.Float()

    # Compliance gates
    requires_food_grade = fields.Boolean()
    requires_medical_grade = fields.Boolean()

    # Geo gate
    radius_miles = fields.Float()
```

### Why It's Valuable

- **More granular than facility-level**: A buyer might accept HDPE pellets but NOT HDPE bales
- **Explicit capability declaration**: Buyers define exactly what they can handle
- **Supports multiple lanes per facility**: One buyer can have 10+ capability lanes

### How to Wire

1. **Populate via UI**: Add capability records in Odoo backend
2. **Sync to Neo4j**: Create `(:Capability)` nodes or edges
3. **Use in matching**: Query capabilities instead of/alongside MaterialProfile

---

## 3. Mack Agent — OUT OF SCOPE

> **Note:** External FastAPI service. Odoo-native matching is the priority. Defer until Odoo native is complete.

### What It Does

`Mack_agent_buyer_matching v7.0.py` is a **FastAPI-based async agent** for external matching:

```python
class BuyerMatchingAgent:
    weights = {
        "polymer_match": 0.30,
        "quality_match": 0.25,
        "volume_match": 0.20,
        "geographic_match": 0.15,
        "trust_compatibility": 0.10,
    }

    async def find_matches(self, intake_data: dict, limit: int = 10):
        buyers = await self._get_active_buyers()
        for buyer in buyers:
            match_score = await self._calculate_match_score(intake_data, buyer)
```

### Scoring Dimensions

| Dimension | Weight | Logic |
|-----------|--------|-------|
| Polymer Match | 30% | Exact match in accepted_polymers list |
| Quality Match | 25% | intake.quality_score vs buyer.quality_requirements |
| Volume Match | 20% | intake.quantity_tons vs buyer.volume_capacity |
| Geographic Match | 15% | Keyword-based (global/national/regional/local) |
| Trust Compatibility | 10% | Trust score difference + payment history |

### Why It's Not Wired

- Uses `app.core.database` — not Odoo ORM
- Designed for FastAPI, not Odoo
- No integration point with `plasticos.intake`

### How to Wire (if needed)

Convert to Odoo service or call via HTTP from Odoo:

```python
# Option A: Convert to Odoo AbstractModel
class PlasticosMackAgent(models.AbstractModel):
    _name = "plasticos.mack.agent"

    def find_matches(self, intake):
        # Port the scoring logic to Odoo
        ...

# Option B: HTTP call to FastAPI
import requests
def match_via_mack(self, intake):
    response = requests.post(
        "http://mack-api/match",
        json=self._intake_to_dict(intake)
    )
    return response.json()
```

---

## 4. Fields Synced But Not Used in Query

### Facility Fields (synced but not gated)

| Field | Synced | Used in Query | Gap |
|-------|--------|---------------|-----|
| `has_wash_line` | ✅ Yes (in expanded sync) | ✅ Yes | — |
| `has_dryer` / `can_reduce_moisture` | ✅ Yes | ✅ Yes | — |
| `has_horizontal_baler` | ✅ Yes | ❌ No | Form handling |
| `has_downstroke_baler` | ✅ Yes | ❌ No | Form handling |
| `has_granulator` | ✅ Yes | ❌ No | Form handling |
| `has_shredder` | ✅ Yes | ❌ No | Form handling |
| `has_extruder` | ✅ Yes | ❌ No | Pelletizing capability |
| `max_monthly_throughput_lbs` | ✅ Yes | ❌ No | Capacity matching |
| `avg_truckload_lbs` | ✅ Yes | ❌ No | Volume optimization |
| `accepted_polymers` | ✅ Yes | ✅ Yes | — |
| `density_min/max` | ✅ Yes | ✅ Yes | — |
| `melt_index_min/max` | ✅ Yes | ✅ Yes | — |
| `contamination_tolerance_pct` | ✅ Yes | ✅ Yes | — |
| `moisture_tolerance_pct` | ✅ Yes | ✅ Yes | — |
| `food_grade_certified` | ✅ Yes | ✅ Yes | — |
| `medical_grade_capable` | ✅ Yes | ✅ Yes | — |
| `iso_certified` | ✅ Yes | ❌ No | Certification gate |
| `sqf_certified` | ✅ Yes | ❌ No | Food safety gate |
| `process_type` | ✅ Yes | ⚠️ Soft signal only | Could be hard gate |

### Quick Wins — Wire These Fields

```cypher
// Add to match query:

// Equipment capability gates
AND (NOT $form_is_bales OR f.has_horizontal_baler = true OR f.has_downstroke_baler = true)
AND (NOT $requires_granulator OR f.has_granulator = true)
AND (NOT $requires_extruder OR f.has_extruder = true)

// Capacity gates
AND (f.max_monthly_throughput_lbs IS NULL
     OR f.max_monthly_throughput_lbs >= $lot_size_lbs)

// Certification gates
AND (NOT $requires_iso OR f.iso_certified = true)
AND (NOT $requires_sqf OR f.sqf_certified = true)
```

---

## 5. Hooks — WIRED but Passive

### What's Built

- `facility_profile_graph_hooks.py` — Triggers sync on facility changes
- `material_profile_graph_hooks.py` — Triggers sync on material changes
- `intake_graph_hooks.py` — Triggers matching on intake creation

### Current State

These hooks exist but may not be fully active. Check `__init__.py` imports.

---

## Wiring Priority Matrix

| Component | Effort | Impact | Priority |
|-----------|--------|--------|----------|
| Wire synced equipment fields into query | LOW | HIGH | 🔴 P1 |
| Add capacity/throughput gates | LOW | MEDIUM | 🟡 P2 |
| Wire certification gates (ISO, SQF) | LOW | LOW | 🟢 P3 |
| Populate `buyer.capability` records | MEDIUM | HIGH | ⏸️ BLOCKED (Odoo install) |
| Port Mack Agent to Odoo | HIGH | LOW | ⏸️ OUT OF SCOPE |

---

## Recommended Next Steps

### Immediate (P1)

1. **Wire equipment fields** — Add form handling gates to Cypher query
2. **Populate buyer capabilities** — Create UI or import script for capability lanes
3. **Test expanded query** — Verify 14 hard gates work correctly

### Short-term (P2)

4. **Hybrid matching** — Combine graph + capability matcher
5. **Capacity gates** — Add throughput/volume constraints
6. **Process type hard gate** — Convert from soft signal to hard gate for MFI-incompatible processes

### Future (P3)

7. **Mack Agent integration** — If external API needed
8. **Trust scoring** — Add transaction history weighting
9. **Full 45-step framework** — Filler science, property degradation
