# Bug Fixes Summary — Odoo 19 Migration

**Generated:** 2026-02-19  
**Workspace:** Odoo_19_ReBoot  
**Branch:** staging

---

## Overview

This document catalogs all bugs identified and fixed during the Odoo 19 migration process. Issues were discovered through:
- Installation log analysis (`installation logs.md`)
- Test execution (`run-odoo-tests.sh`)
- XML validation errors during module loading

---

## Bug #1: One2many Field `mode="list,form"` Deprecated

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
odoo.tools.convert.ParseError: Field "max_monthly_throughput_lbs" does not exist in model "res.partner"
```

**Root Cause:**  
Odoo 19 no longer supports `mode="list,form"` attribute on One2many fields in views.

**Files Fixed:**
- `plasticos_facility_profile/views/facility_profile_views.xml`
- `plasticos_material_profile/views/material_profile_views.xml`

**Fix:**  
Replaced `mode="list,form"` with explicit inline `<list>` and `<form>` view definitions.

---

## Bug #2: Payment Term Field Rename (`days` → `nb_days`)

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ValueError: Invalid field 'days' in 'account.payment.term.line'
```

**Root Cause:**  
Odoo 19 renamed `days` field to `nb_days` in `account.payment.term.line` model.

**Files Fixed:**
- `plasticos_foundation_seed/data/payment_terms.xml`

**Fix:**  
Updated all payment term records:
- Changed `days` → `nb_days`
- Changed `value: 'balance'` → `value: 'percent'` with `value_amount: 100.0`
- Added early discount fields where applicable

---

## Bug #3: Cron Field `numbercall` Removed

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ValueError: Invalid field 'numbercall' in 'ir.cron'
```

**Root Cause:**  
Odoo 19 removed the `numbercall` field from `ir.cron` model.

**Files Fixed (8 total):**
- `plasticos_automation/data/sale_approval_cron.xml`
- `plasticos_automation/data/stock_alert_cron.xml`
- `plasticos_automation/data/invoice_reminder_cron.xml`
- `plasticos_automation/data/contract_renewal_cron.xml`
- `plasticos_logistics_automation/data/cron_supplier_followup.xml`
- `plasticos_logistics_automation/data/cron_load_sla.xml`
- `plasticos_logistics_automation/data/cron_broker_followup.xml`
- `plasticos_logistics_automation/data/cron_missing_docs.xml`

**Fix:**  
Removed `<field name="numbercall">-1</field>` from all cron XML files.

---

## Bug #4: SQL Constraints Syntax Change

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
WARNING: Model attribute '_sql_constraints' is no longer supported
ImportError: cannot import name 'Constraint' from 'odoo.orm'
```

**Root Cause:**  
Odoo 19 changed constraint syntax from `_sql_constraints` list to `models.Constraint` class attributes.

**Files Fixed:**
- `plasticos_automation/models/automation_config.py`

**Fix:**  
```python
# Before (Odoo 18)
from odoo.orm import Constraint
_constraints = [Constraint("name", "CHECK(...)", "message")]

# After (Odoo 19)
_singleton_check = models.Constraint("CHECK(...)", "message")
```

---

## Bug #5: Search View `<group expand="0">` Invalid

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
odoo.tools.convert.ParseError: Invalid view plasticos.web.lead.search definition
```

**Root Cause:**  
Odoo 19's stricter RelaxNG validation rejects `<group>` with `expand` attribute in search views.

**Files Fixed:**
- `plasticos_web_leads/views/web_lead_views.xml`

**Fix:**  
Removed `<group expand="0" string="Group By">` wrapper and moved filter elements directly under `<search>`.

---

## Bug #6: `target="inline"` Deprecated for Actions

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ValueError: Wrong value for ir.actions.act_window.target: 'inline'
```

**Root Cause:**  
Odoo 19 removed `inline` as a valid value for `ir.actions.act_window.target`.

**Files Fixed:**
- `plasticos_web_leads/views/web_lead_config_views.xml`
- `plasticos_automation/views/automation_config_views.xml`

**Fix:**  
Changed `<field name="target">inline</field>` → `<field name="target">current</field>`

---

## Bug #7: `widget="json"` Deprecated

**Status:** ✅ FIXED  
**Severity:** WARNING (view rendering issues)  
**Error:**  
Widget not rendering properly in form views.

**Root Cause:**  
Odoo 19 deprecated `widget="json"` for displaying JSON fields.

**Files Fixed:**
- `plasticos_web_leads/views/web_lead_views.xml` (3 fields)
- `plasticos_material_profile/views/material_profile_views.xml` (1 field)
- `plasticos_matching/views/match_result_views.xml` (1 field)

**Fix:**  
Changed `widget="json"` → `widget="text"`

---

## Bug #8: Missing Base Form View for Inheritance

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ValueError: External ID not found in the system: plasticos_documents.view_document_form
```

**Root Cause:**  
`plasticos_documents_extension` tried to inherit from `view_document_form` which didn't exist in `plasticos_documents`.

**Files Fixed:**
- `plasticos_documents/views/document_views.xml`

**Fix:**  
Added the missing form view definition with appropriate fields from `plasticos.document` model.

---

## Bug #9: Circular Module Dependency

**Status:** ✅ FIXED  
**Severity:** CRITICAL (infinite loop during install)  
**Error:**
```
odoo.exceptions.UserError: Recursion error in modules dependencies!
```

**Root Cause:**  
Circular dependency between modules:
- `plasticos_documents` → `plasticos_transaction`
- `plasticos_transaction` → `plasticos_documents`

**Files Fixed:**
- `plasticos_transaction/__manifest__.py`

**Fix:**  
Removed `plasticos_documents` from `plasticos_transaction` dependencies. The correct architecture is:
```
plasticos_transaction (base) ← plasticos_documents (extends it)
```

---

## Bug #10: Menu Item Load Order

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ValueError: External ID not found in the system: plasticos_documents.menu_documents_root
```

**Root Cause:**  
`document_tag_views.xml` loaded before `document_views.xml`, but referenced `menu_documents_root` defined in the latter.

**Files Fixed:**
- `plasticos_documents/__manifest__.py`

**Fix:**  
Reordered data files so `document_views.xml` loads before `document_tag_views.xml`.

---

## Bug #11: Non-Existent Module in Test Script

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks test execution)  
**Error:**
```
WARNING: invalid module names, ignored: plasticos_documents_extension
UserError: module "plasticos_dev_tools" depends on "plasticos_documents_extension" which is not available
```

**Root Cause:**  
`plasticos_documents_extension` was listed in test script and as a dependency, but the module doesn't exist in the repo.

**Files Fixed:**
- `run-odoo-tests.sh`
- `plasticos_dev_tools/__manifest__.py`

**Fix:**  
- Removed `plasticos_documents_extension` from module list
- Changed `plasticos_dev_tools` dependency to `plasticos_documents`

---

## Bug #12: Cron `model_id` Missing Module Prefix

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ValueError: External ID "model_plasticos_load" not found in the system
```

**Root Cause:**  
Cron job XML files referenced model IDs without the module prefix. Odoo 19 requires fully qualified external IDs.

**Files Fixed:**
- `plasticos_logistics/data/cron.xml`
- `plasticos_documents/data/cron.xml`
- `plasticos_transaction/data/cron_missing_docs.xml`

**Fix:**  
Changed `ref="model_plasticos_load"` → `ref="plasticos_logistics.model_plasticos_load"` (added module prefix to all model_id references).

---

## Bug #13: Cron XML Missing `noupdate` Wrapper

**Status:** ✅ FIXED  
**Severity:** WARNING (data overwritten on upgrade)  
**Error:**  
No error, but cron records would be reset on module upgrade.

**Root Cause:**  
`plasticos_logistics/data/cron.xml` was missing the `<data noupdate="1">` wrapper, causing cron configurations to be overwritten on module upgrades.

**Files Fixed:**
- `plasticos_logistics/data/cron.xml`

**Fix:**  
Added `<data noupdate="1">` wrapper around cron records and added `<field name="active">True</field>` to each cron job.

---

## Bug #14: Soft Reference Required for Cross-Module Model Access

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
KeyError: 'plasticos.transaction'
```

**Root Cause:**  
`plasticos_documents/models/document.py` directly accessed `self.env["plasticos.transaction"]` without checking if the module was installed. This created a hard dependency that conflicted with the circular dependency fix.

**Files Fixed:**
- `plasticos_documents/models/document.py`

**Fix:**  
Added soft reference check before accessing the model:
```python
# Before
tx = self.env["plasticos.transaction"].search(...)

# After
if "plasticos.transaction" in self.env:
    tx = self.env["plasticos.transaction"].search(...)
```

---

## Non-Bug Issues (Informational)

### FileNotFoundError for Filestore Attachments
**Status:** NOT A BUG  
8 missing PDF files in filestore — these are demo data attachments that don't exist in the test environment. Normal behavior.

### Deprecation Warnings (XMLRPC/JSONRPC)
**Status:** INFORMATIONAL  
Warnings about deprecated `/xmlrpc` and `/jsonrpc` endpoints. No action required.

### SMS API Errors
**Status:** EXPECTED  
SMS sending fails without IAP credits configured. Expected in test environment.

### AI Fields Skipped
**Status:** EXPECTED  
AI analysis fields skipped when `OPENAI_API_KEY` not configured.

---

## Files Modified Summary

| Module | Files Changed |
|--------|---------------|
| `plasticos_automation` | 5 files (crons, config model, views) |
| `plasticos_commission` | 0 files |
| `plasticos_dev_tools` | 4 files (manifest, tests) |
| `plasticos_documents` | 4 files (manifest, views, document.py, cron.xml) |
| `plasticos_facility_profile` | 1 file (views) |
| `plasticos_foundation_seed` | 1 file (payment_terms.xml) |
| `plasticos_intake` | 0 files |
| `plasticos_logistics` | 1 file (cron.xml) |
| `plasticos_logistics_automation` | 4 files (crons) |
| `plasticos_matching` | 1 file (views) |
| `plasticos_material_profile` | 1 file (views) |
| `plasticos_offer` | 0 files |
| `plasticos_partner_import` | 0 files |
| `plasticos_polymer` | 0 files |
| `plasticos_transaction` | 2 files (manifest, cron_missing_docs.xml) |
| `plasticos_web_leads` | 2 files (views) |

---

## Odoo 19 Migration Checklist

Based on bugs found, check your modules for:

- [ ] `mode="list,form"` on One2many fields → use inline views
- [ ] `days` field in payment terms → rename to `nb_days`
- [ ] `numbercall` in ir.cron → remove entirely
- [ ] `_sql_constraints` list → use `models.Constraint` class attributes
- [ ] `<group expand="...">` in search views → remove group wrapper
- [ ] `target="inline"` in actions → use `target="current"`
- [ ] `widget="json"` → use `widget="text"`
- [ ] Circular dependencies between modules
- [ ] Data file load order in manifest
- [ ] Missing base views for inherited views
- [ ] Cron `model_id` refs need module prefix (e.g., `module.model_name`)
- [ ] Cron XML files should have `<data noupdate="1">` wrapper
- [ ] Cross-module model access needs soft reference check (`if "model" in self.env`)
- [ ] Root `__init__.py` must import `models` directory
- [ ] `models/__init__.py` must import ALL `.py` files in directory
- [ ] External IDs must be unique across all XML files (no collisions between models)
- [ ] Remove redundant `res.partner.category` records that duplicate canonical lookup tables

---

## Verification Status

**Last Verified:** 2026-02-19  
**Verification Method:** Automated grep/search across all modules

| Pattern | Result |
|---------|--------|
| `mode="list,form"` | ✅ None found |
| `<field name="days">` in payment terms | ✅ None found |
| `numbercall` in cron XML | ✅ None found |
| `_sql_constraints` list format | ✅ None found (converted to `models.Constraint`) |
| `<group expand=` in search views | ✅ None found |
| `target="inline"` | ✅ None found |
| `widget="json"` | ✅ None found |
| Circular dependencies | ✅ None detected |
| Empty root `__init__.py` | ✅ All modules import models |
| Missing model imports | ✅ All `.py` files imported |
| External ID collisions | ✅ None found |
| Redundant `res.partner.category` | ✅ Removed (source_type_, form_, color_) |
| Python syntax errors | ✅ All files pass `py_compile` |
| XML parsing errors | ✅ All files parse correctly |

**Total Bugs Fixed:** 19

---

## Bug #15: Empty `__init__.py` Prevents Model Registration

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ParseError: No matching record found for external id 'model_plasticos_source_type' in field 'Model'
```

**Root Cause:**  
`plasticos_foundation_seed/__init__.py` was empty, so the `models/` directory was never imported and models like `plasticos.source.type` were not registered.

**Files Fixed:**
- `plasticos_foundation_seed/__init__.py`

**Fix:**  
Added `from . import models` to register the models directory.

---

## Bug #16: External ID Collision Between Models

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
ParseError: For external id plasticos_foundation_seed.source_type_post_consumer when trying to create/update a record of model res.partner.category found record of different model plasticos.source.type
```

**Root Cause:**  
Same external ID (`source_type_post_consumer`) was used in two different XML files for two different models:
- `reference_types_data.xml` → `plasticos.source.type`
- `material_taxonomy.xml` → `res.partner.category`

**Files Fixed:**
- `plasticos_foundation_seed/data/material_taxonomy.xml`

**Fix:**  
Removed all redundant `res.partner.category` records that duplicated canonical lookup tables:
- Deleted `source_type_*` records (duplicated `plasticos.source.type`)
- Deleted `form_*` records (duplicated `plasticos.form.type`)
- Deleted `color_*` records (duplicated `plasticos.color.type`)
- Kept only `polymer_*` and `material_type_*` which don't have canonical models

---

## Bug #17: Missing Model Imports in `__init__.py`

**Status:** ✅ FIXED  
**Severity:** CRITICAL (blocks module loading)  
**Error:**
```
Model not registered / field not found errors
```

**Root Cause:**  
Several `models/__init__.py` files were missing imports for Python files in the same directory.

**Files Fixed:**
- `plasticos_documents/models/__init__.py` — added `validation_matrix`
- `plasticos_transaction/models/__init__.py` — added `transaction_docs`

**Fix:**  
Added missing imports to ensure all model files are registered.

---

## Bug #18: Redundant Partner Categories Duplicating Canonical Models

**Status:** ✅ FIXED  
**Severity:** CRITICAL (external ID collision)  
**Error:**
```
ParseError: For external id plasticos_foundation_seed.source_type_post_consumer when trying to create/update a record of model res.partner.category found record of different model plasticos.source.type
```

**Root Cause:**  
`material_taxonomy.xml` created `res.partner.category` records that duplicated canonical lookup tables:
- `source_type_*` → duplicated `plasticos.source.type`
- `form_*` → duplicated `plasticos.form.type`
- `color_*` → duplicated `plasticos.color.type`

**Files Fixed:**
- `plasticos_foundation_seed/data/material_taxonomy.xml`

**Fix:**  
Removed all redundant `res.partner.category` records:
- Deleted `category_forms`, `category_source_types`, `category_colors` parent categories
- Deleted all `form_*`, `source_type_*`, `color_*` child records
- Kept only `polymer_*` and `material_type_*` (no canonical models exist for these)

**Records Removed:**
- 15 form type records (BAG, BALE, CHOP, etc.)
- 14 source type records (Clean, Post-Consumer, Post-Industrial, etc.)
- 14 color records (Black, Blue, Clear, etc.)
- 3 parent category records

---

## Bug #19: Constraint Syntax Update (Additional Files)

**Status:** ✅ FIXED  
**Severity:** WARNING (deprecation warning)  
**Error:**
```
WARNING: Model attribute '_sql_constraints' is no longer supported
```

**Root Cause:**  
Additional files still using old `_sql_constraints = [...]` tuple format instead of `models.Constraint` class attributes.

**Files Fixed:**
- `plasticos_foundation_seed/models/reference_types.py` (5 model classes)
- `plasticos_automation/models/automation_config.py`

**Fix:**  
```python
# Before (deprecated)
_sql_constraints = [
    ("code_uniq", "unique(code)", "Code must be unique."),
]

# After (Odoo 19)
_code_uniq = models.Constraint(
    "unique(code)",
    "Code must be unique.",
)
```
