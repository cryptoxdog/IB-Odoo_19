# Complete Test File Plan — Every Module, Every Test File

**Generated:** 2026-03-04
**Status:** Phase 0 — TODO Plan Locked
**Total Test Files:** 58 files across 15 modules

---

## P0 — Revenue-path models (Priority: CRITICAL)

### plasticos_transaction/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_transaction_states.py` | 10 | 10-state machine: draft→active→closed, draft→cancelled, verify invalid skips raise UserError |
| `test_transaction_constraints.py` | 4 | unique name SQL constraint, commission_override_pct range (0.0-1.0) |
| `test_transaction_computes.py` | 19 | All computed fields: margin, total, commission, display_name, weight reconciliation |
| `test_transaction_crud.py` | 8 | create with partner sync, write guards, unlink protection on posted |
| `test_commission_rules.py` | 6 | percentage 0-100, unique rep+active constraint, calculation against transaction |

**State Machine Tests (`test_transaction_states.py`):**
```python
STATES = [
    "draft", "active", "pending_supplier", "supplier_ready",
    "in_progress", "in_transit", "delivered", "invoiced",
    "closed", "cancelled"
]

VALID_TRANSITIONS = {
    "draft": ["active", "cancelled"],
    "active": ["pending_supplier", "in_progress", "cancelled"],
    # ... full map
}
```

**Computed Fields (`test_transaction_computes.py`):**
- `weight_variance_percent` — depends on expected_weight, actual_weight
- `gross_weight`, `final_weight`, `weight_source` — priority: scale > buyer > supplier
- `tare_per_unit`, `total_tare` — unit_type defaults
- `weight_discrepancy_pct`, `weight_discrepancy_flagged` — >5% threshold
- `light_weight_deduction`, `dead_freight_chargeback`
- `revenue_total`, `purchase_cost_total`, `freight_cost_total`, `cost_total`
- `gross_margin`, `net_margin`
- `commission_amount` — rule-based or override
- `compliance_status` — document-based
- `line_count`, `historical_sale_total`, `historical_purchase_total`, `historical_margin`
- `supplier_profile_id`, `buyer_profile_id`, `buyer_facility_id`, `supplier_material_id`

---

### plasticos_logistics/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_load_states.py` | 10 | Full 10-state pipeline (draft→closed), invalid transitions, message_post on each step |
| `test_dispatch_transitions.py` | 6 | Forward-only validation (ALLOWED_TRANSITIONS map) |
| `test_load_reports.py` | 3 | BOL pickup/delivery render without error |
| `test_rate_memory.py` | 4 | unique carrier+lane+date constraint |

**State Machine (`test_load_states.py`):**
```python
LOAD_STATES = [
    "draft", "awaiting_ready", "ready_confirmed", "rate_confirmed",
    "scheduled", "dispatched", "picked_up", "delivered",
    "closed", "exception"
]
```

**Actions to Test:**
- `action_confirm_ready(user_name)` — sets ready_confirmed_by, ready_confirmed_at
- `action_confirm_rate(rate)` — sets rate_amount, rate_confirmed_at, calls `_store_rate_memory()`
- `action_schedule(pickup_dt, delivery_dt)` — sets pickup_datetime, delivery_datetime
- `action_dispatch()` — requires scheduled or rate_confirmed state
- `action_close()` — requires BOL documents attached

---

### plasticos_offer/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_offer_states.py` | 8 | draft→sent→responded→accepted, draft→cancelled, reset_to_draft |
| `test_offer_constraints.py` | 3 | price >= 0, quantity >= 0 SQL constraints |
| `test_offer_expiry_cron.py` | 3 | cron marks old sent offers as expired |

**State Machine (`test_offer_states.py`):**
```python
OFFER_STATES = [
    "draft", "sent", "responded", "accepted",
    "rejected", "expired", "cancelled"
]

VALID_TRANSITIONS = {
    "draft": ["sent", "cancelled"],
    "sent": ["responded", "accepted", "rejected", "expired", "cancelled"],
    "responded": ["accepted", "rejected", "cancelled"],
    "rejected": ["draft"],  # reset_to_draft
    "cancelled": ["draft"],  # reset_to_draft
}
```

**Computed Fields:**
- `total_value` — price_per_lb × quantity_lbs
- `days_until_expiry` — valid_until - today
- `display_name` — "Offer: {intake} → {buyer} [{state}]"

---

### plasticos_claims/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_claim_states.py` | 8 | pending→in_progress→resolved→archived, escalate flow, reopen |
| `test_claim_constraints.py` | 3 | unique name, resolution_note required on resolve |
| `test_claim_computes.py` | 4 | days_open, is_overdue, recovery_rate, related partner fields |

**State Machine (`test_claim_states.py`):**
```python
CLAIM_STATES = [
    "pending", "in_progress", "escalated", "resolved", "archived"
]

VALID_TRANSITIONS = {
    "pending": ["in_progress", "escalated"],
    "in_progress": ["escalated", "resolved"],
    "escalated": ["in_progress", "resolved"],
    "resolved": ["archived", "in_progress"],  # reopen
    "archived": ["in_progress"],  # reopen
}
```

**Validation:**
- `_check_resolution_note()` — resolution_note required when state='resolved'

---

### plasticos_intake/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_intake_crud.py` | 6 | create with partner+facility linkage, display_name assembly |
| `test_intake_computes.py` | 8 | Computed fields: pricing, quantity summaries, profile |
| `test_intake_onchanges.py` | 9 | 9 onchanges: polymer→form defaults, partner→facility cascade |
| `test_intake_constraints.py` | 3 | quantity_per_load_lbs > 0, loads_per_month >= 0 |

**Computed Fields (`test_intake_computes.py`):**
- `name` — auto-generated from partner/facility + polymer
- `company_display` — partner name or pending company name
- `match_count`, `selected_count` — from match_line_ids
- `best_match_score` — max of match_line_ids.match_score
- `has_residue` — contamination_pct > 0

**Onchanges (`test_intake_onchanges.py`):**
1. `_onchange_partner_id()` — auto-select facility when company has exactly one
2. `_onchange_facility_id()` — auto-select contact from preferred memory
3. `_onchange_contact_id()` — save contact to preferred memory
4. `_onchange_lead_source_id()` — sync to partner
5. `_onchange_material_profile()` — pre-fill snapshot fields
6. `_onchange_material_attributes()` — sync boolean fields
7. `_onchange_has_metal()` — sync attributes
8. `_onchange_is_metalized()` — sync attributes
9. `_onchange_has_fr()` — sync attributes

---

### plasticos_material_profile/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_registry_uniqueness.py` | 8 | All 8 SQL unique constraints: polymer.code, form.code, color.code, etc. |
| `test_profile_crud.py` | 5 | create profile with polymer+form+partner, unique triple constraint |
| `test_profile_computes.py` | 6 | display_name, full_description, partner counts |
| `test_partner_material_sync.py` | 4 | custom write() partner sync loop guard |

**Registry Unique Constraints (`test_registry_uniqueness.py`):**
1. `plasticos.polymer` — `unique(code)`
2. `plasticos.material.form` — `unique(code)`
3. `plasticos.material.color` — `unique(code)`
4. `plasticos.source.type` — `unique(code)`
5. `plasticos.process.type` — `unique(code)`
6. `plasticos.filler.type` — `unique(code)`
7. `plasticos.packaging.type` — `unique(code)`
8. `plasticos.material.attribute` — `unique(code)`

**Profile Constraint:**
- `unique(partner_id, polymer_id, form_id)` — one profile per polymer+form per facility

---

## P1 — Supporting workflow models

### plasticos_documents/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_document_lifecycle.py` | 5 | verify→override→supersede transitions |
| `test_document_rules.py` | 4 | unique rule per tag+model+client |
| `test_document_tags.py` | 3 | unique code constraint |
| `test_compliance_service.py` | 5 | check transaction docs vs required rules |

**Actions (`test_document_lifecycle.py`):**
- `action_verify()` — sets verified=True, verified_by, verified_at
- `action_override(reason)` — requires group_documents_manager, sets override=True
- `action_supersede(new_doc_id)` — sets is_current=False, superseded_by

**Computed Fields:**
- `is_expired` — expiry_date < today

---

### plasticos_facility_profile/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_facility_crud.py` | 5 | create profile, unique partner constraint, partner sync |
| `test_facility_constraints.py` | 4 | density_min < density_max, melt_index_min < max |
| `test_equipment_types.py` | 3 | unique code constraint |
| `test_partner_types.py` | 3 | unique code, lead source mapping |

---

### plasticos_matching/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_match_result_states.py` | 5 | pending→accepted, pending→rejected, no backwards |
| `test_match_result_constraints.py` | 4 | score 0-100, confidence 0-100, unique match per run |

**State Machine (`test_match_result_states.py`):**
```python
MATCH_STATES = ["pending", "accepted", "rejected", "expired"]

VALID_TRANSITIONS = {
    "pending": ["accepted", "rejected", "expired"],
    # No backward transitions from terminal states
}
```

**SQL Constraints:**
- `unique(intake_id, buyer_partner_id, run_id)`
- `check(score >= 0 AND score <= 100)`
- `check(confidence >= 0 AND confidence <= 100)`

---

### plasticos_buyer_match_engine/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_matcher.py` | 10 | ✅ Already exists, already imported |
| `test_match_exclusion.py` | 4 | create exclusion, verify it blocks matching |
| `test_graph_sync_log.py` | 3 | log creation and search |

---

### plasticos_enrichment/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_normalization.py` | 8 | ✅ Already exists — UNCOMMENT in __init__.py |
| `test_injection.py` | 6 | ✅ Already exists — UNCOMMENT in __init__.py |
| `test_enrichment_run_states.py` | 6 | state machine: draft→crawling→extracting→validated→injected |

**State Machine (`test_enrichment_run_states.py`):**
```python
ENRICHMENT_STATES = [
    "draft", "crawling", "extracting", "validated", "injected", "error"
]
```

---

### plasticos_web_leads/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_web_lead_states.py` | 5 | received→intake_created, received→skipped, error handling |
| `test_web_lead_constraints.py` | 3 | unique lead_id |
| `test_web_lead_actions.py` | 5 | force_hot, retry_triage, force_create_intake |

**State Machine (`test_web_lead_states.py`):**
```python
WEB_LEAD_STATES = ["received", "intake_created", "skipped", "error"]
```

**Actions (`test_web_lead_actions.py`):**
- `action_retry_processing()` — only for state='error'
- `action_force_create_intake()` — manual override
- `action_retry_triage()` — re-run AI pipeline
- `action_force_hot()` — override COLD to HOT

---

### plasticos_automation/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_automation_config.py` | 4 | config CRUD, defaults, validation |
| `test_automation_log.py` | 3 | log creation on action execution |

---

### plasticos_security_base/tests/

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 5 | ✅ Skeleton (done) |
| `test_record_rules.py` | 6 | sales rep sees only own transactions, x_private partner isolation |
| `test_group_membership.py` | 4 | three role groups exist and restrict access |

---

### plasticos_inference_engine/tests/ (pure Python, no ORM)

| File | Tests | Description |
|------|-------|-------------|
| `test_module_install.py` | 3 | ✅ Skeleton (done) — minimal, no ORM models |
| `test_inference_engine.py` | 8 | InferenceEngine.infer() for HDPE, PP — deterministic results from YAML KB |
| `test_polymer_aliases.py` | 6 | alias resolution: "polyethylene"→PE, "polypropylene"→PP |
| `test_tier_engine.py` | 5 | quality tier assignment: commodity/engineering/specialty |
| `test_kb_loader.py` | 4 | all YAML KB files load without error, every polymer covered |

**Note:** These tests use `unittest.TestCase` or `TransactionCase` but don't require ORM models.

---

## Summary

| Priority | Modules | Test Files | Total Tests |
|----------|---------|------------|-------------|
| P0 | 6 | 30 | ~150 |
| P1 | 9 | 28 | ~100 |
| **Total** | **15** | **58** | **~250** |

---

## Implementation Order

### Phase 1: P0 Revenue-Path (Week 1)
1. `plasticos_transaction` — 6 files
2. `plasticos_logistics` — 5 files
3. `plasticos_offer` — 4 files
4. `plasticos_claims` — 4 files
5. `plasticos_intake` — 5 files
6. `plasticos_material_profile` — 5 files

### Phase 2: P1 Supporting (Week 2)
7. `plasticos_documents` — 5 files
8. `plasticos_facility_profile` — 5 files
9. `plasticos_matching` — 3 files
10. `plasticos_buyer_match_engine` — 4 files
11. `plasticos_enrichment` — 4 files
12. `plasticos_web_leads` — 4 files
13. `plasticos_automation` — 3 files
14. `plasticos_security_base` — 3 files
15. `plasticos_inference_engine` — 5 files

---

## Test Patterns

### State Machine Test Pattern
```python
@tagged("post_install", "-at_install")
class TestStateTransitions(TransactionCase):
    def test_valid_transition(self):
        """Test valid state transition."""
        record = self.env["model.name"].create({...})
        record.action_method()
        self.assertEqual(record.state, "expected_state")

    def test_invalid_transition_raises(self):
        """Invalid transition should raise UserError."""
        record = self.env["model.name"].create({...})
        record.state = "wrong_state"
        with self.assertRaises(UserError):
            record.action_method()
```

### Constraint Test Pattern
```python
@tagged("post_install", "-at_install")
class TestConstraints(TransactionCase):
    def test_unique_constraint(self):
        """Duplicate should raise IntegrityError."""
        self.env["model.name"].create({"code": "test"})
        with self.assertRaises(IntegrityError):
            self.env["model.name"].create({"code": "test"})

    def test_check_constraint(self):
        """Invalid value should raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["model.name"].create({"value": -1})
```

### Computed Field Test Pattern
```python
@tagged("post_install", "-at_install")
class TestComputes(TransactionCase):
    def test_computed_field(self):
        """Computed field should calculate correctly."""
        record = self.env["model.name"].create({
            "field_a": 100,
            "field_b": 50,
        })
        self.assertEqual(record.computed_field, 150)
```

---

## __init__.py Updates Required

Each module's `tests/__init__.py` needs to import all test files:

```python
# plasticos_transaction/tests/__init__.py
from . import test_module_install
from . import test_transaction_states
from . import test_transaction_constraints
from . import test_transaction_computes
from . import test_transaction_crud
from . import test_commission_rules
```

---

## Next Steps

1. **Create test directories** for modules without `tests/` folder
2. **Generate test files** following the patterns above
3. **Update `__init__.py`** files to import all tests
4. **Run tests** with `odoo-bin -d test_db --test-enable -i module_name`
5. **Fix failures** and iterate
