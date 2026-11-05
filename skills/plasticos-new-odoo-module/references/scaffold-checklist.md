<!-- L9_META
skill_schema: 1
parent: plasticos-new-odoo-module
layer: reference
role: checklist
tags: [plasticos, odoo, scaffold, manifest, acl]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Module Scaffold Checklist

## Steps

1. Create directory: `plasticos_{name}/`
2. Create `__manifest__.py`:
   - `name`: "PlasticOS {Name}"
   - `version`: "19.0.1.0.0"
   - `license`: "LGPL-3"
   - `author`: "Igor Beylin"
   - `category`: "PlasticOS"
   - `depends`: layer-correct list (never depend on higher layers)
   - `data`: all XML/CSV files
   - `installable`: True (False for dev-only)
3. Create `__init__.py` with `from . import models`
4. Create `models/__init__.py` importing all model files
5. Model files: constants at top, `_name = "plasticos.{model_name}"`, `_description`, `mail.thread` for business models
6. Create `security/ir.model.access.csv`
7. Create `views/` (form, list, search)
8. Create `data/` seed XML (`noupdate="1"`, external IDs)
9. Update `config/odoo_module_order.yaml`
10. Run checks (see SKILL.md Validation)

## Final Checklist

- [ ] Module name uses `plasticos_` prefix
- [ ] Model names use `plasticos.` prefix
- [ ] External IDs use `plasticos_{module}.` prefix
- [ ] Dependencies declared and acyclic
- [ ] ACL exists for all models
- [ ] No deprecated Odoo patterns
- [ ] Wiring and circular-dep checks pass
