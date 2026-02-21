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

# Invalid field references
- transaction_id on models that don't have it
- Domains referencing non-existent fields

# Rate limiting issues
- geo_localize() calls without delays
- External API calls in create/write methods

# Duplicate labels
- Multiple fields with same string= value

# Enterprise dependencies
- model="documents.folder/tag/facet" (requires Enterprise)
- _inherit = "documents.document" (requires Enterprise)
- depends: ["documents", "documents_account", "hr_expense", "sign", "planning"]
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
