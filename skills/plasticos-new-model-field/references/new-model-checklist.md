<!-- L9_META
skill_schema: 1
parent: plasticos-new-model-field
layer: reference
role: checklist
tags: [plasticos, odoo, model, acl, wiring]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# New Model Checklist

## Adding a New Model to Existing Module

1. Create `plasticos_{module}/models/{model_name}.py`
2. Import in `models/__init__.py`
3. `_name = "plasticos.{model_name}"` — string literal only
4. Add `_description`; inherit `mail.thread` for business models
5. Create `security/ir.model.access.csv` — read full CSV first; match id-column format
6. Create views (form + list + search minimum)
7. Add menu in `views/menu.xml`
8. Add XML/CSV to `__manifest__.py` `data` list
9. Bump manifest version
10. Write tests using `TransactionCase`; create fixtures in `setUpClass` (never `skipTest`)

## Pre-Commit Checklist

- [ ] Model names use `plasticos.` prefix
- [ ] External IDs use `plasticos_{module}.` prefix
- [ ] Every `Many2one` has `ondelete=`
- [ ] Manifest `depends` includes all cross-module comodels
- [ ] ACL in same module as model definition
- [ ] No deprecated Odoo patterns (`_sql_constraints`, `@api.one`, `<tree>`)

## Validation Commands

```bash
python3 scripts/check_module_wiring.py
python3 ci/check_circular_deps.py
python3 ci/check_field_integrity.py
pre-commit run --all-files
```
