# PlasticOS IB-Odoo 19 — Gap Analysis & Module Consolidation Report

**Date:** 2026-02-19
**Scope:** All 21 module directories on `staging`, 6 open PRs (#12–#17), 17 PRs total
**Method:** Full source audit — manifests, models, views, security, data, dependencies, field alignment

---

## Executive Summary

The repo contains **17 installable modules** on staging plus **4 unmerged modules** on feature branches and **1 new module** in PR #17. The architecture is sound at the domain-model level, but there are **7 critical gaps** that would block or degrade a production deployment, **5 consolidation opportunities** that reduce module count by ~30%, and **12 secondary issues** ranging from field-type mismatches to missing tests.

**Recommended module count after consolidation: 13 (down from 21).**

---

## Part 1: Critical Gaps (Functional Blockers)

### GAP-1: No Intake → Transaction Link

**Severity: CRITICAL**
**Current state:** `plasticos.transaction` has no `intake_id` field. `plasticos.intake` has no `transaction_id` field. The entire pipeline (Intake → Match → Offer → Transaction) is **broken at the last step**. When an offer is accepted, `action_accept()` simply sets state to "accepted" — it does not create a transaction, sale order, or purchase order.

**Impact:** The core revenue pipeline has no way to convert accepted offers into billable transactions. This is the single highest-leverage gap in the system.

**Fix:** Add `intake_id` (Many2one) and `offer_id` (Many2one) to `plasticos.transaction`. Add `action_create_transaction()` to `plasticos.offer` that generates the transaction spine with SO/PO from offer terms.

---

### GAP-2: Reference Type Models Are Orphaned

**Severity: HIGH**
**Current state:** `plasticos_foundation_seed` defines 5 reference type models (`plasticos.form.type`, `plasticos.color.type`, `plasticos.source.type`, `plasticos.process.type`, `plasticos.deal.type`) with seed data. **Zero modules reference them via relational fields.** Instead, `plasticos.intake`, `plasticos.material.profile`, and `plasticos.facility.profile` all use inline `Selection` fields or `Char` fields for the same concepts.

**Impact:** The seed data is installed but never queried. Selection values are hardcoded in 3+ modules and will drift. Adding a new polymer form requires editing Python code in multiple files instead of adding one XML record.

**Fix:** Either (a) convert intake/material_profile/facility_profile to use `Many2one` fields pointing to these reference models, or (b) delete the reference type models and keep the Selection approach (simpler, but less extensible). Recommendation: **option (a)** — it is the correct Odoo pattern and enables user-managed reference data.

---

### GAP-3: `plasticos_polymer` Ghost Module on Staging

**Severity: HIGH**
**Current state:** The `plasticos_polymer/` directory on staging contains **only `__pycache__` files** — no `__init__.py`, no `__manifest__.py`, no source code. The polymer model (`plasticos.polymer`) was correctly consolidated into `plasticos_material_profile` (commit `d162b95`), but the empty directory was not cleaned up. Meanwhile, `plasticos_documents_native` (PR #13) still declares `plasticos_polymer` as a dependency.

**Impact:** PR #13 cannot install because it depends on a module that does not exist on staging. The ghost directory will confuse developers.

**Fix:** Delete `plasticos_polymer/` from staging. Update `plasticos_documents_native` manifest to depend on `plasticos_material_profile` instead.

---

### GAP-4: `sales_rep_id` Referenced in Security Rules but Missing from Transaction Model

**Severity: HIGH**
**Current state:** PR #12 (`plasticos_security_base`) defines a record rule `rule_transaction_sales_rep` with domain `[('sales_rep_id', '=', user.id)]`. The `plasticos.transaction` model has **no `sales_rep_id` field**. This will cause a runtime error when any Sales Rep user tries to access transactions.

**Impact:** The entire RBAC system for Sales Reps will crash on transaction access.

**Fix:** Add `sales_rep_id = fields.Many2one("res.users", ...)` to `plasticos.transaction`, or change the record rule to use `create_uid`.

---

### GAP-5: Intake `polymer`/`form`/`color`/`source_type` Are Char Fields — Not Validated

**Severity: HIGH**
**Current state:** `plasticos.intake` uses `fields.Char` for `polymer`, `form`, `color`, and `source_type`. These accept any freeform text. Meanwhile, `plasticos.material.profile` uses `fields.Selection` with controlled lists for the same concepts. The normalizer has to do runtime validation to catch mismatches.

**Impact:** Dirty data enters the system at the intake level. The normalizer catches some errors, but matching and reporting will produce inconsistent results when intake records use "HDPE" vs "hdpe" vs "High Density PE".

**Fix:** Convert intake fields to either (a) `Selection` matching material_profile, or (b) `Many2one` to the reference type models (see GAP-2). The web_lead module already maps freeform text to canonical codes — the intake model should enforce the same codes.

---

### GAP-6: Four Modules Stuck on Feature Branches — Not Merged to Staging

**Severity: MEDIUM-HIGH**
**Current state:** Four modules exist only on feature branches with only `__pycache__` artifacts on staging:

| Module | Branch | PR | Status |
|---|---|---|---|
| `plasticos_polymer` | `feat/plasticos-polymer-master` | #4 (CLOSED) | Consolidated into material_profile — ghost dir remains |
| `plasticos_security_base` | `feat/plasticos-security-base` | #12 (OPEN) | Complete module, not merged |
| `plasticos_documents_native` | `feat/plasticos-documents-native` | #13 (OPEN) | Complete module, not merged |
| `plasticos_geolocalize` | `feat/plasticos-geolocalize` | #15 (OPEN) | Complete module, not merged |

**Impact:** These modules are not available for testing or integration. PR #13 depends on PR #12 and the (deleted) polymer module. Merge order matters.

**Fix:** Merge in dependency order: #12 → #15 → #14 → #16 → #13 → #17. Delete `plasticos_polymer/` ghost directory first.

---

### GAP-7: `numbercall` Field in Normalizer Cron (Deprecated in Odoo 19)

**Severity: MEDIUM**
**Current state:** `plasticos_intake_normalizer/data/cron_batch_normalize.xml` uses `<field name="numbercall">-1</field>`. This field was deprecated in Odoo 19 and will cause a warning or error on install.

**Impact:** Module install may fail or log warnings.

**Fix:** Remove the `numbercall` field from the cron XML.

---

## Part 2: Module Consolidation Opportunities

Since you are still in build phase and have not deployed, now is the optimal time to reduce module count. Fewer modules = simpler dependency graph, faster install, easier debugging.

### CONSOLIDATION-1: Merge `plasticos_automation` + `plasticos_logistics_automation` → `plasticos_automation`

**Current state:** Two separate automation modules:
- `plasticos_automation`: sale approvals, invoice reminders, contract renewals, stock alerts (4 crons)
- `plasticos_logistics_automation`: supplier follow-ups, broker follow-ups, load SLA monitoring (3 crons)

Both follow the same pattern: cron jobs + x_ extension fields on standard Odoo models + automation log. `logistics_automation` already depends on `plasticos_logistics` and `plasticos_transaction`.

**Effort:** ~3 files moved, 1 manifest merged. **Ratio: 3 files → eliminates 1 module + simplifies dependency graph.**

**Recommendation:** Merge into single `plasticos_automation` module. Add `plasticos_logistics` and `plasticos_transaction` as dependencies.

---

### CONSOLIDATION-2: Merge `plasticos_documents_extension` into `plasticos_documents`

**Current state:** Two modules for the same domain:
- `plasticos_documents`: base document model, tags, rules, compliance service (4 models)
- `plasticos_documents_extension`: expiry tracking, versioning, validation matrix, transaction docs (4 model extensions)

The extension module adds `x_` fields to the base document model via `_inherit`. Since you haven't deployed, there is no upgrade migration concern — you can put everything in one module.

**Effort:** ~4 files moved, 1 manifest merged, data files combined. **Ratio: 4 files → eliminates 1 module.**

**Recommendation:** Merge into single `plasticos_documents`. The `plasticos_documents_native` bridge module (PR #13) then depends on one module instead of two.

---

### CONSOLIDATION-3: Merge `plasticos_commission` into `plasticos_transaction`

**Current state:** `plasticos_commission` contains exactly 2 files:
- `commission_rule.py`: 15 lines, one model with 4 fields
- `commission_service.py`: 8 lines, one AbstractModel with one method

The transaction module is the **only consumer** of commission. It already depends on `plasticos_commission`. The commission rule model has a single constraint and the service has a single method.

**Effort:** 2 files moved. **Ratio: 2 files → eliminates 1 module + 1 dependency edge.**

**Recommendation:** Merge into `plasticos_transaction`. Commission is not a standalone domain — it is a feature of the transaction lifecycle.

---

### CONSOLIDATION-4: Merge `plasticos_web_leads` + `plasticos_web_lead_ai_triage` (PR #17) → `plasticos_web_leads`

**Current state:** PR #17 creates a new `plasticos_web_lead_ai_triage` module that extends the web lead model with AI classification, image analysis, and Cognito webhook. Both modules operate on the same domain (inbound web leads) and share the same data flow.

**Effort:** PR #17 is not yet merged. Combine during merge. **Ratio: 1 merge → eliminates 1 module before it ships.**

**Recommendation:** Merge AI triage functionality into `plasticos_web_leads` as an extension of the existing model. Single module for the entire web lead pipeline.

---

### CONSOLIDATION-5: Delete `plasticos_polymer` Ghost Directory

**Current state:** Empty directory with only `__pycache__` files. The polymer model lives in `plasticos_material_profile`.

**Effort:** `rm -rf plasticos_polymer/`. **Ratio: 1 command → eliminates confusion + unblocks PR #13.**

**Recommendation:** Delete immediately.

---

### Consolidation Summary

| Action | Before | After | Modules Eliminated |
|---|---|---|---|
| CONSOL-1: automation + logistics_automation | 2 | 1 | 1 |
| CONSOL-2: documents + documents_extension | 2 | 1 | 1 |
| CONSOL-3: commission → transaction | 2 | 1 | 1 |
| CONSOL-4: web_leads + ai_triage | 2 | 1 | 1 |
| CONSOL-5: delete polymer ghost | 1 | 0 | 1 |
| **Total** | **9** | **4** | **5** |

**Post-consolidation module count: 21 − 5 = 16 directories, 13 installable modules** (plus `dev_tools` non-installable and `reports/` non-module).

---

## Part 3: Secondary Issues

### SEC-1: Inconsistent Constraint Syntax

**Issue:** `plasticos_foundation_seed` and `plasticos_automation` use the old `_sql_constraints` list syntax. All other modules use the Odoo 19 `models.Constraint` class syntax.

**Fix:** Convert the 7 `_sql_constraints` instances to `models.Constraint`.

---

### SEC-2: Empty ACL File in `plasticos_logistics_automation`

**Issue:** `security/ir.model.access.csv` contains only the header row — no actual ACL entries. The module adds `x_` fields to existing models via `_inherit`, so it technically does not define new models. However, the empty file is misleading.

**Fix:** Either add a comment explaining why it is empty, or remove it from the manifest if no new models exist.

---

### SEC-3: Security Groups Are Fragmented Across Modules

**Issue:** Security groups are defined in 5 different modules:
- `plasticos_automation`: `group_plasticos_automation_manager`
- `plasticos_documents`: `group_documents_user`, `group_documents_manager`
- `plasticos_documents_extension`: `group_documents_extension_manager`
- `plasticos_logistics_automation`: `group_logistics_automation_manager`
- `plasticos_transaction`: `group_plasticos_manager`, `group_plasticos_commission_manager`

PR #12 (`plasticos_security_base`) defines 3 business roles (`Sales Rep`, `Logistics`, `Accounting`) but does **not** consolidate or reference the existing per-module groups.

**Fix:** After merging PR #12, refactor all module-specific groups to inherit from the `security_base` roles. Example: `group_plasticos_manager` should imply `group_sales_rep` + `group_logistics` + `group_accounting`.

---

### SEC-4: No Tests for Any Module on Staging

**Issue:** The only test files on staging are in `plasticos_dev_tools/tests/` which is a non-installable module. Zero installable modules have test suites. PR #17 is the first to include tests.

**Fix:** Add at minimum smoke tests for the core pipeline: intake creation, normalization, matching, offer lifecycle, transaction close. This is a deployment risk.

---

### SEC-5: `plasticos.material.profile` Restricts `partner_id` to Facilities Only

**Issue:** The `_check_partner_is_facility` constraint raises `ValidationError` if `partner_id.parent_id` is False. Per the user's requirement, intakes should link to **both parent companies and child facilities**. A parent company that is also a processing facility (flagship site) cannot have a material profile.

**Fix:** Relax the constraint to allow partners where `parent_id` is False but `x_facility_role` is set, or remove the constraint entirely and rely on domain filtering in views.

---

### SEC-6: `plasticos.facility.profile` Has Same Restriction

**Issue:** `facility_profile.py` has `domain="[('parent_id','!=',False)]"` on `partner_id`, preventing flagship parent companies from having capability profiles.

**Fix:** Change domain to `['|', ('parent_id', '!=', False), ('x_facility_role', '!=', False)]` to allow parent companies with facility roles.

---

### SEC-7: Offer Does Not Link to Transaction on Accept

**Issue:** `action_accept()` in `plasticos.offer` sets state to "accepted" but does not create any downstream records. There is no `transaction_id` field on the offer model.

**Fix:** Add `transaction_id` field and implement `action_create_transaction()` that generates the transaction spine from offer terms. (Related to GAP-1.)

---

### SEC-8: Transaction Has No `partner_id` / `supplier_id` / `buyer_id`

**Issue:** `plasticos.transaction` has `sale_order_id` and `purchase_order_ids` but no direct partner references. To find the buyer, you must traverse `sale_order_id.partner_id`. This makes reporting, filtering, and record rules harder.

**Fix:** Add `supplier_id` and `buyer_id` as stored related fields from the SO/PO, or as direct Many2one fields set during transaction creation.

---

### SEC-9: `plasticos.dispatch` Model Is Orphaned

**Issue:** `plasticos.dispatch` exists in `plasticos_logistics` but has no relationship to `plasticos.load`. The load model has its own state machine that covers the dispatch lifecycle. The dispatch model appears to be a leftover from an earlier design.

**Fix:** Either connect dispatch to load (load.dispatch_id) or remove the dispatch model if load already covers the workflow.

---

### SEC-10: Foundation Seed `material_taxonomy.xml` May Conflict with Polymer Data

**Issue:** `plasticos_foundation_seed/data/material_taxonomy.xml` seeds material-related reference data. `plasticos_material_profile/data/polymer_data.xml` seeds polymer records. If both are installed, there may be duplicate or conflicting seed data for the same concepts.

**Fix:** Audit both XML files for overlap. The polymer master should be the single source of truth for polymer types.

---

### SEC-11: `plasticos_partner_import` Has No Views

**Issue:** The module defines an import service (AbstractModel) but no views, no menu items, and no wizard. Users have no way to trigger the import from the UI.

**Fix:** Add a transient model (wizard) with a file upload field and a "Run Import" button, plus a menu item under Settings or Contacts.

---

### SEC-12: Intake `facility_id` Domain Does Not Include Parent (on staging)

**Issue:** On staging, `facility_id` domain is `[('parent_id', '=', partner_id)]` which excludes the parent company itself. PR #16 (not yet merged) fixes this to `['|', ('id', '=', partner_id), ('parent_id', '=', partner_id)]`.

**Fix:** Merge PR #16.

---

## Part 4: Recommended Execution Order

Applying the L9 First-Order Thinking protocol — **functional before cosmetic, dependency order, highest leverage first**:

| Priority | Action | Type | Effort | Unlocks |
|---|---|---|---|---|
| **P0** | GAP-1: Add intake_id/offer_id to transaction + action_create_transaction on offer | Functional | 2 files | Revenue pipeline |
| **P0** | CONSOL-5: Delete `plasticos_polymer/` ghost | Cleanup | 1 command | PR #13 merge |
| **P1** | GAP-4: Add `sales_rep_id` to transaction (or fix record rule) | Functional | 1 field | PR #12 merge |
| **P1** | GAP-7: Remove `numbercall` from normalizer cron | Bug fix | 1 line | Clean install |
| **P1** | SEC-1: Convert `_sql_constraints` → `models.Constraint` | Consistency | 7 edits | Clean install |
| **P2** | CONSOL-1: Merge automation modules | Consolidation | 3 files | Simpler graph |
| **P2** | CONSOL-2: Merge documents modules | Consolidation | 4 files | Simpler graph |
| **P2** | CONSOL-3: Merge commission into transaction | Consolidation | 2 files | Simpler graph |
| **P2** | CONSOL-4: Merge web_lead modules | Consolidation | During PR #17 | Simpler graph |
| **P2** | GAP-2: Convert Char/Selection → Many2one for reference types | Architecture | 3 modules | Data integrity |
| **P2** | GAP-5: Convert intake Char fields to Selection or Many2one | Architecture | 1 module | Data integrity |
| **P3** | SEC-3: Consolidate security groups under security_base roles | Security | 5 modules | RBAC coherence |
| **P3** | SEC-4: Add smoke tests for core pipeline | Quality | New files | Deploy confidence |
| **P3** | SEC-5/6: Relax facility-only constraints for flagship sites | Functional | 2 files | Flagship support |
| **P3** | SEC-8: Add supplier_id/buyer_id to transaction | UX | 1 file | Reporting |
| **P3** | SEC-9: Resolve orphaned dispatch model | Cleanup | 1 file | Clean architecture |
| **P3** | SEC-11: Add import wizard for partner_import | UX | 1 file | User access |
| **P4** | Merge PRs in order: #12 → #14 → #15 → #16 → #13 → #17 | Integration | 6 PRs | Full platform |

---

## Part 5: Dependency Graph (Current State)

```
plasticos_foundation_seed ──────────────────────────────────┐
plasticos_material_profile ─────────────────────────────────┤
  ├── plasticos_facility_profile                            │
  │     ├── plasticos_matching ←── plasticos_intake         │
  │     │     └── plasticos_offer                           │
  │     └── plasticos_partner_import                        │
  ├── plasticos_intake ──────────────────────────────┐      │
  │     ├── plasticos_intake_normalizer ─────────────┤      │
  │     ├── plasticos_web_leads                      │      │
  │     └── plasticos_geolocalize [PR #15]           │      │
  └── plasticos_transaction ─────────────────────────┘      │
        ├── plasticos_logistics                             │
        ├── plasticos_documents ────────────────────────────┘
        │     └── plasticos_documents_extension
        └── plasticos_commission

plasticos_automation (standalone)
plasticos_logistics_automation (depends: logistics + transaction)
plasticos_security_base [PR #12] (standalone)
plasticos_documents_native [PR #13] (depends: documents + polymer[BROKEN] + security_base)
```

---

## Part 6: Model Registry (30 Custom Models)

| Model | Module | Type | ACL |
|---|---|---|---|
| `plasticos.automation.config` | automation | Model | Yes |
| `plasticos.automation.log` | automation | Model | Yes |
| `plasticos.commission.rule` | commission | Model | Yes |
| `plasticos.compliance.service` | documents | AbstractModel | N/A |
| `plasticos.document` | documents | Model | Yes |
| `plasticos.document.rule` | documents | Model | Yes |
| `plasticos.document.tag` | documents | Model | Yes |
| `plasticos.document.validation.matrix` | documents_extension | Model | Yes |
| `plasticos.equipment.type` | facility_profile | Model | Yes |
| `plasticos.facility.profile` | facility_profile | Model | Yes |
| `plasticos.form.type` | foundation_seed | Model | Yes |
| `plasticos.color.type` | foundation_seed | Model | Yes |
| `plasticos.source.type` | foundation_seed | Model | Yes |
| `plasticos.process.type` | foundation_seed | Model | Yes |
| `plasticos.deal.type` | foundation_seed | Model | Yes |
| `plasticos.intake` | intake | Model | Yes |
| `plasticos.normalizer.config` | intake_normalizer | Model | Yes |
| `plasticos.load` | logistics | Model | Yes |
| `plasticos.dispatch` | logistics | Model | Yes |
| `plasticos.rate.memory` | logistics | Model | Yes |
| `plasticos.match.result` | matching | Model | Yes |
| `plasticos.material.profile` | material_profile | Model | Yes |
| `plasticos.polymer` | material_profile | Model | Yes |
| `plasticos.offer` | offer | Model | Yes |
| `plasticos.partner.import.service` | partner_import | AbstractModel | N/A |
| `plasticos.partner.import.validation` | partner_import | AbstractModel | N/A |
| `plasticos.transaction` | transaction | Model | Yes |
| `plasticos.transaction.line` | transaction | Model | Yes |
| `plasticos.audit.cron` | transaction | Model | Yes |
| `plasticos.transaction.import.service` | transaction | AbstractModel | N/A |
| `plasticos.web.lead` | web_leads | Model | Yes |
| `plasticos.web.lead.config` | web_leads | Model | Yes |
| `plasticos.document.sync` | documents_native [PR #13] | AbstractModel | N/A |

---

*Report generated by gap analysis of `staging` branch at commit `d162b95`.*
