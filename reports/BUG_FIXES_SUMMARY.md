# Bug Fixes Summary - Odoo 19 Migration

**Generated:** 2026-02-21
**Branch:** staging

## Bug Patterns Identified & Fixed

### 1. Odoo 19 Breaking Changes

| Bug Type | Example | Fix |
|----------|---------|-----|
| `category_id` removed from `res.groups` | `security_groups.xml` line 14 | Remove `category_id` field from all group records |
| `_sql_constraints` deprecated | Warning in logs | Use `model.Constraint` instead (TODO) |

### 2. Invalid Field References

| Bug Type | Example | Fix |
|----------|---------|-----|
| Wrong relational field in domain | `transaction_id.user_id` on `plasticos.load` | Use correct field: `sale_order_id.user_id` |
| Duplicate field labels | `source_type` vs `source_type_id` same label | Rename one field's `string=` attribute |

### 3. External API Rate Limiting

| Bug Type | Example | Fix |
|----------|---------|-----|
| No rate limiting on geocoding | Auto-geocode on create/write | Disable auto-geocode, use nightly cron with delays |
| 429 Too Many Requests | OpenStreetMap Nominatim | Add `time.sleep(1.1)` between requests |

### 4. Missing Dependencies

| Bug Type | Example | Fix |
|----------|---------|-----|
| External Python dependency not declared | `openai` package | Add to `requirements.txt` and `__manifest__.py` |

### 5. XML Data File Issues

| Bug Type | Example | Fix |
|----------|---------|-----|
| Missing `<data>` wrapper | `email_templates.xml` | Add `<data noupdate="1">` wrapper |
| Deprecated cron field | `numbercall` field | Remove deprecated field |

### 6. Enterprise Module Dependencies

| Bug Type | Example | Fix |
|----------|---------|-----|
| `KeyError: 'documents.folder'` | `plasticos_documents_native` tries to create records for Enterprise-only model | Set `installable: False` until Enterprise `documents` is manually installed via Apps |
| Enterprise model in XML data | `model="documents.folder"`, `model="documents.tag"` | Keep in Enterprise-only module with proper dependency declaration |

### 7. Duplicate Field Labels

| Bug Type | Example | Fix |
|----------|---------|-----|
| Two fields with same label | `polymer` and `polymer_id` both labeled "Polymer" | Add `string="Polymer Code"` to computed field |
| Warning in logs | `Two fields (polymer, polymer_id) have the same label` | Differentiate labels with "Code" suffix for computed Selection fields |

### 8. Manifest Warnings

| Bug Type | Example | Fix |
|----------|---------|-----|
| Missing author/license | `l9_trace/__manifest__.py` | Add `author`, `license`, `summary` fields |

---

## Commits (This Session)

| Commit | Description |
|--------|-------------|
| `32dded2` | fix: disable auto-geocoding, add rate limiting to cron |
| `8052bb5` | fix: remove category_id from res.groups (Odoo 19) |
| `ce82795` | fix: correct record rule domain - sale_order_id not transaction_id |

---

## Patterns to Scan For

```
# Odoo 19 breaking changes
- category_id in res.groups XML
- _sql_constraints in Python models
- @api.depends("id") — compute methods cannot depend on 'id'

# Invalid field references
- transaction_id on models that don't have it
- Domains referencing non-existent fields
- Views referencing fields that don't exist in model

# Model-View-Data alignment
- fields.Selection values not matching data XML code values
- View field names not matching model field names
- External ID references to non-existent records

# Rate limiting issues
- geo_localize() calls without delays
- External API calls in create/write methods

# Duplicate labels
- Multiple fields with same string= value

# Enterprise dependencies
- model="documents.folder/tag/facet" (requires Enterprise)
- _inherit = "documents.document" (requires Enterprise)
- depends: ["documents", "documents_account", "hr_expense", "sign", "planning"]

# Orphaned code
- Root-level folders not registered in any __manifest__.py
- Models referencing non-existent models (e.g., sm.tx, sm.logistics.automation)
- Legacy code from previous versions (Linda Logistics v6.0)
```

---

## Scan Results

### Fixed This Session

| File | Issue | Fix |
|------|-------|-----|
| `plasticos_security_base/security/security_groups.xml` | `category_id` on `res.groups` (Odoo 19 removed) | Removed all `category_id` fields |
| `plasticos_security_base/security/record_rules.xml` | Invalid field `transaction_id` on `plasticos.load` | Changed to `sale_order_id` |
| `plasticos_geolocalize/models/res_partner_geo.py` | No rate limiting on geocoding API | Disabled auto-geocode, added 1.1s delay in cron |
| `plasticos_buyer_match_engine/models/buyer_capability.py` | `_sql_constraints` deprecated | Converted to `models.Constraint` |
| `plasticos_buyer_match_engine/models/buyer_capability.py` | Duplicate field labels (source_type, polymer, form) | Added "Code" suffix to computed field labels |
| `plasticos_documents_native/__manifest__.py` | `KeyError: 'documents.folder'` — Enterprise module not installed | Set `installable: False` until Enterprise `documents` is manually installed via Apps |
| `plasticos_material_profile/models/material_profile.py` | Duplicate field labels (polymer, form, color, source_type) | Added "Code" suffix to computed Selection field labels |

### Fixed 2026-02-21 (Session 2)

| File | Issue | Fix |
|------|-------|-----|
| `plasticos_intake/models/intake.py` | `NotImplementedError: Compute method cannot depend on field 'id'` | Removed `"id"` from `@api.depends` decorator |
| `plasticos_material_profile/views/material_profile_views.xml` | `ParseError: Field "contains_metal" does not exist` | Changed to `has_metal`, added `is_metalized` |
| `plasticos_material_profile/views/material_profile_views.xml` | Field `packaging_type` not found | Changed to `packaging_type_id` |
| `plasticos_material_profile/views/material_profile_views.xml` | Missing fields in views | Added `origin_form_id`, `material_attribute_ids` |
| `plasticos_material_profile/models/material_profile.py` | `fields.Selection` values not aligned with data XMLs | Updated polymer, form, color, source_type selections to match data files |
| `plasticos_material_profile/models/packaging_type.py` | `_sql_constraints` deprecated (Odoo 19) | Converted to `models.Constraint` |
| `plasticos_material_profile/models/material_attribute.py` | `_sql_constraints` deprecated (Odoo 19) | Converted to `models.Constraint` |
| `plasticos_product/data/product_category_data.xml` | `ValueError: External ID not found: product.product_category_all` | Removed `parent_id` reference |
| `plasticos_product/models/product_template.py` | Field naming inconsistency | Renamed `material_form_id` → `form_id`, `material_color_id` → `color_id`, `source_type_id` → `type_id`, `material_attribute_ids` → `attribute_ids` |
| `plasticos_product/data/product_data.xml` | Field references misaligned with model | Updated all field references to match renamed fields |
| `wizards/` (root folder) | Orphaned legacy code from Linda Logistics v6.0 | Deleted entire folder (non-functional, referenced non-existent models `sm.tx`, `sm.logistics.automation`) |
| `plasticos_transaction/wizards/` | Missing bulk update wizard | Created new properly integrated wizard with correct model references |

### Created 2026-02-21 (Session 3) - Bulk Action Wizards

| Module | Wizard | Purpose |
|--------|--------|---------|
| `plasticos_claims/wizards/` | `claim_bulk_update_wizard.py` | Bulk status change, assignment, and escalation for claims |
| `plasticos_logistics/wizards/` | `load_bulk_update_wizard.py` | Bulk status updates for logistics loads |
| `plasticos_offer/wizards/` | `offer_bulk_action_wizard.py` | Bulk send/accept/reject/cancel for offers |
| `plasticos_web_leads/wizards/` | `lead_bulk_action_wizard.py` | Bulk force-hot, retry triage, mark skipped for web leads |

**Files created per wizard:**
- `wizards/__init__.py` — Python package init
- `wizards/*_wizard.py` — TransientModel with bulk action logic
- `views/*_wizard_views.xml` — Form view + binding action to list view

**Files updated per module:**
- `__init__.py` — Added `from . import wizards`
- `__manifest__.py` — Added wizard view XML to `data` list
- `security/ir.model.access.csv` — Added ACL for wizard model

### Verified Clean (No Issues Found)

| Pattern | Files Scanned | Result |
|---------|---------------|--------|
| `@api.one` / `@api.multi` (deprecated) | All `.py` | None found |
| `numbercall` (deprecated cron field) | All `.xml` | None found |
| Missing `author`/`license` in manifests | All `__manifest__.py` | All present |
| `category_id` on `res.groups` | All `.xml` | Fixed (only 1 file had it) |
| Enterprise model references | All `.xml` | Only in `plasticos_documents_native` (isolated, fixed) |

### 9. Field Type Mismatches

| Bug Type | Example | Fix |
|----------|---------|-----|
| Char fields instead of Many2one | `polymer`, `form`, `color` as Char in intake | Convert to Many2one referencing master registries |
| View references wrong field name | `packaging_type` in view but `packaging_type_id` in model | Fix view to use correct field name |

### 10. Data Overlap / Drift

| Bug Type | Example | Fix |
|----------|---------|-----|
| Same value in multiple master data files | `Loose` in both forms and packaging | Remove from forms, keep in packaging only |
| Duplicate conceptual values | `Reusable` in source_type and attributes | Remove from source_type, keep as attribute |
| `Mixed` in multiple places | source_type, attributes, colors | Remove from source_type (keep in attributes and colors - different context) |

### 11. Missing Fields in Views

| Bug Type | Example | Fix |
|----------|---------|-----|
| Model field not in view | `origin_form_id` defined but not visible | Add to Material section in form view |
| `material_attribute_ids` not visible | Many2many field exists but not in UI | Add with `widget="many2many_tags"` |

---

### Fixed 2026-02-21 (Session 4) - Critical Audit Fixes

| File | Issue | Fix |
|------|-------|-----|
| `plasticos_logistics/data/cron.xml` | Missing module prefix in `model_id` ref | Added `plasticos_logistics.` prefix |
| `plasticos_documents/data/cron.xml` | Missing module prefix in `model_id` ref | Added `plasticos_documents.` prefix |
| `plasticos_logistics/models/sale_order_inherit.py` | Empty inherit file (dead code) | Deleted file + removed import |
| `plasticos_transaction/models/purchase_inherit.py` | Empty inherit file (dead code) | Deleted file + removed import |
| `plasticos_transaction/models/load_inherit.py` | Empty inherit file (dead code) | Deleted file + removed import |
| `plasticos_transaction/models/account_move_inherit.py` | Empty inherit file (dead code) | Deleted file + removed import |
| `plasticos_material_profile/models/material_profile.py` | Namespace drift (`PlastosMaterialProfile`) | Fixed to `PlasticosMaterialProfile` |
| `plasticos_transaction/models/transaction.py` | Missing denormalized profile refs (slow 3-hop traversals) | Added `supplier_profile_id`, `buyer_profile_id` computed fields |
| `plasticos_product/models/product_template.py` | Product-material disconnect | Added `material_profile_id` link |
| `plasticos_product/data/product_data.xml` | XML syntax error - nested quotes in `eval` + missing module prefix | Fixed `ref("attr_clean")` → `ref('plasticos_material_profile.attr_clean')` (18 occurrences) |
| `plasticos_claims/data/claim_cron.xml` | Missing module prefix in `model_id` ref | Added `plasticos_claims.` prefix |

### 12. Namespace Drift

| Bug Type | Example | Fix |
|----------|---------|-----|
| Class name missing "ico" | `PlastosMaterialProfile` | Fix to `PlasticosMaterialProfile` |
| Inconsistent naming | `PlastosFacilityCapability` vs `PlasticosFacilityProfile` | Standardize all to `Plasticos*` |

### 13. XML Cron Model References

| Bug Type | Example | Fix |
|----------|---------|-----|
| Missing module prefix in `model_id` ref | `ref="model_plasticos_load"` | Add module prefix: `ref="plasticos_logistics.model_plasticos_load"` |
| Cross-module ref without namespace | `ref="model_plasticos_document"` | Add module prefix: `ref="plasticos_documents.model_plasticos_document"` |

### 14. Empty Inherit Files (Dead Code)

| Bug Type | Example | Fix |
|----------|---------|-----|
| Inherit file with only class stub | `class SaleOrder(models.Model): _inherit = "sale.order"` with no fields | Delete file + remove from `__init__.py` |
| Orphaned imports | `from . import sale_order_inherit` pointing to deleted file | Remove import line |

### 15. XML eval() Quote Issues

| Bug Type | Example | Fix |
|----------|---------|-----|
| Nested double quotes in eval | `eval="[(6, 0, [ref("attr_clean")])]"` | Use single quotes inside: `ref('attr_clean')` |
| Missing module prefix in ref() | `ref('attr_clean')` | Add module: `ref('plasticos_material_profile.attr_clean')` |

### 16. Missing Denormalized Fields

| Bug Type | Example | Fix |
|----------|---------|-----|
| Slow multi-hop traversals | Transaction → Partner → Profile requires 3 queries | Add denormalized `supplier_profile_id`, `buyer_profile_id` |
| Product-material disconnect | Products have no link to material profiles | Add `material_profile_id` to `product.template` |

---

### Remaining Warnings (Cosmetic)

| Warning | Location | Status |
|---------|----------|--------|
| `invalid module names: plasticos_foundation_seed` | Database | Stale DB reference - safe to ignore |
| `claims_security.xml` line 11 `category_id` | `res.groups.privilege` model | Valid - this model DOES have `category_id` |

---

## Commits (This Session)

| Commit | Description |
|--------|-------------|
| `32dded2` | fix: disable auto-geocoding, add rate limiting to cron |
| `8052bb5` | fix: remove category_id from res.groups (Odoo 19) |
| `ce82795` | fix: correct record rule domain - sale_order_id not transaction_id |
| `35c636e` | feat: Add material attributes, packaging types, convert intake to dropdowns |
| `62de211` | fix: Minor model adjustments for material attributes and product |
| `cb01665` | chore: Remove wizards folder |

---

## Fixed This Session (2026-02-21)

| File | Issue | Fix |
|------|-------|-----|
| `plasticos_intake/models/intake.py` | `polymer`, `form`, `color` were Char fields (not dropdowns) | Converted to Many2one: `polymer_id`, `form_id`, `color_id` |
| `plasticos_intake/views/intake_views.xml` | View referenced `packaging_type` but model has `packaging_type_id` | Fixed field name in view |
| `plasticos_intake/views/intake_views.xml` | `origin_form_id` not visible in UI | Added to Material section |
| `plasticos_intake/views/intake_views.xml` | `material_attribute_ids` not visible | Added with many2many_tags widget |
| `plasticos_material_profile/data/material_form_data.xml` | `Loose` duplicated in forms AND packaging | Removed from forms (keep in packaging only) |
| `plasticos_material_profile/data/source_type_data.xml` | `Reusable`, `Mixed`, `Unknown` duplicated as source types AND attributes | Removed from source_type (keep as attributes) |
| `plasticos_material_profile/data/source_type_data.xml` | `No Value` was source type but should be attribute | Moved to attributes |
| `plasticos_material_profile/data/material_attribute_data.xml` | `Contaminated` renamed | Changed to `Oily` per user request |

---

## Pre-Commit Hooks Added (2026-02-21)

**Files created:**
- `.pre-commit-config.yaml` — Hook configuration
- `pyproject.toml` — Ruff linting rules (Odoo-friendly)

### Hooks Enabled

| Hook | What it catches |
|------|-----------------|
| `ruff` | Python syntax errors, unused imports, undefined names, style issues |
| `ruff-format` | Python formatting consistency |
| `check-xml` | **XML syntax errors** (unescaped `&`, malformed tags) |
| `check-yaml` | YAML syntax errors |
| `trailing-whitespace` | Trailing whitespace |
| `end-of-file-fixer` | Missing newline at EOF |
| `check-merge-conflict` | Leftover merge conflict markers |

### Bugs Fixed by Pre-Commit (Would Have Been Caught)

| File | Bug | Hook That Catches It |
|------|-----|----------------------|
| `plasticos_product/data/product_data.xml:655` | Unescaped `&` in `PC & PMMA` | `check-xml` |
| `plasticos_product/data/product_data.xml:1136` | Unescaped `&` in `PP Tubs & Lids` | `check-xml` |

### Bugs NOW Caught by `check_odoo_patterns.sh` (Custom CI)

These are Odoo-specific bugs that ruff/mypy cannot catch, but our custom CI script now detects:

| Bug Type | Example | CI Check |
|----------|---------|----------|
| `@api.depends("id")` | Odoo 19 disallows depending on `id` | ✅ `check_odoo_patterns.sh` |
| `_sql_constraints` deprecation | Odoo 19 requires `models.Constraint` | ✅ `check_odoo_patterns.sh` |
| `category_id` on `res.groups` | Removed in Odoo 19 | ✅ `check_odoo_patterns.sh` |
| `@api.one/@api.multi` | Removed in Odoo 13+ | ✅ `check_odoo_patterns.sh` |
| `numbercall` on ir.cron | Deprecated cron field | ✅ `check_odoo_patterns.sh` |
| Unescaped `&` in XML | Causes parse errors | ✅ `check_odoo_patterns.sh` |
| Empty `__init__.py` in modules | Models won't load | ✅ `check_odoo_patterns.sh` |
| Namespace drift (`PlastoS` vs `PlasticoS`) | Inconsistent class naming | ✅ `check_odoo_patterns.sh` |
| Empty inherit files | Dead code | ✅ `check_odoo_patterns.sh` |
| Cron `model_id` missing module prefix | `ref="model_plasticos_*"` without module | ✅ `check_odoo_patterns.sh` |
| XML `eval` with nested double quotes | `eval="[ref("id")]"` | ✅ `check_odoo_patterns.sh` |

### Bugs That Still Require Odoo Runtime Validation

These cannot be caught by static analysis — require `odoo -i module --test-enable`:

| Bug Type | Example | Why Static Tools Miss It |
|----------|---------|--------------------------|
| Invalid field references in domains | `transaction_id.user_id` on model without `transaction_id` | Requires model schema knowledge |
| Field name mismatches (view ↔ model) | `packaging_type` in view but `packaging_type_id` in model | XML views aren't type-checked against Python models |
| External ID references to non-existent records | `ref="product.product_category_all"` (doesn't exist) | Requires database state |
| Enterprise module dependencies | `model="documents.folder"` | Requires installed module list |

### Python Issues Found by Ruff (Not Blocking, Style)

| Issue Type | Count | Example |
|------------|-------|---------|
| `B018` Useless expression | ~20 | `__manifest__.py` files with bare dict |
| `UP031` Use format specifiers | ~10 | `"Hello %s" % name` → `f"Hello {name}"` |
| `W291` Trailing whitespace | ~15 | Whitespace at end of lines |
| `W293` Blank line with whitespace | ~5 | Empty lines containing spaces |
| `F841` Unused variable | 2 | `record = ...` never used |
| `F821` Undefined name | 2 | `env` used without import |

### Usage

```bash
# Runs automatically on git commit
git commit -m "your message"

# Run manually on all files
pre-commit run --all-files

# Run specific hook only
pre-commit run check-xml --all-files
pre-commit run ruff --all-files
```

### Recommendation: Future Bug Prevention

| Prevention Method | Bugs Prevented | Status |
|-------------------|----------------|--------|
| **Pre-commit hooks** (now active) | XML syntax, Python syntax, formatting | ✅ Active |
| **`check_odoo_patterns.sh`** (custom CI) | Odoo 19 breaking changes, namespace drift, dead code, cron refs, eval quotes | ✅ Active (11 checks) |
| **Odoo test suite** (`-i module --test-enable`) | Field references, domains, views, external IDs | Manual |
| **Manual review checklist** | Enterprise deps, complex business logic | Manual |

### CI Checks Summary (11 Total)

| # | Check | Pattern | Bug # |
|---|-------|---------|-------|
| 1 | `_sql_constraints` | Deprecated in Odoo 17+ | #1 |
| 2 | `@api.depends("id")` | Disallowed in Odoo 19 | #1 |
| 3 | `@api.one/@api.multi` | Removed in Odoo 13+ | #1 |
| 4 | `category_id` on `res.groups` | Removed in Odoo 19 | #1 |
| 5 | `numbercall` on ir.cron | Deprecated | #5 |
| 6 | Unescaped `&` in XML | Parse errors | #5 |
| 7 | Empty `__init__.py` | Models won't load | #5 |
| 8 | Namespace drift | `PlastoS` vs `PlasticoS` | #12 |
| 9 | Empty inherit files | Dead code | #14 |
| 10 | Cron `model_id` refs | Missing module prefix | #13 |
| 11 | XML `eval` quotes | Nested double quotes | #15 |
