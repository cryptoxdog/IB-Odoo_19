---
name: plasticos-new-odoo-module
description: create a new plasticos odoo 19 module with proper structure, manifest, acl, views, and layer-correct dependencies. use when scaffolding a new plasticos_* addon or bootstrapping module files.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [odoo, module, scaffold, plasticos]
owner: igor_beylin
status: active
version: 1.0.0
updated: 2026-06-04
---

# New Odoo Module

## Steps

1. **Determine the layer** (1–5) this module belongs to per ARCHITECTURE.md
2. **Create directory**: `plasticos_{name}/`
3. **Create `__manifest__.py`**:
   - `name`: "PlasticOS {Name}"
   - `version`: "19.0.1.0.0"
   - `license`: "LGPL-3"
   - `author`: "Igor Beylin"
   - `category`: "PlasticOS"
   - `depends`: list all required modules (check layer — never depend on higher layers)
   - `data`: list all XML/CSV data files
   - `installable`: True (False for dev-only)
4. **Create `__init__.py`** with `from . import models`
5. **Create `models/__init__.py`** importing all model files
6. **Create model files** in `models/` following patterns:
   - Model string constants at top: `RES_PARTNER = "res.partner"`
   - `_name = "plasticos.{model_name}"`
   - `_description` required
   - `_inherit = ["mail.thread"]` for business models
   - Fields with `help=`, `tracking=True`, `index=True` where appropriate
7. **Create `security/ir.model.access.csv`** with ACL for all groups
8. **Create `views/` directory** with form/tree/search views
9. **Create `data/` directory** for seed data XML (noupdate="1", external IDs)
10. **Update `config/odoo_module_order.yaml`** with install position
11. **Run checks**:
    ```bash
    python3 scripts/check_module_wiring.py
    python3 ci/check_circular_deps.py
    pre-commit run --all-files
    ```

## Checklist
- [ ] Module name uses `plasticos_` prefix
- [ ] Model names use `plasticos.` prefix
- [ ] External IDs use `plasticos_{module}.` prefix
- [ ] `__manifest__.py` dependencies declared
- [ ] `security/ir.model.access.csv` exists
- [ ] No deprecated Odoo patterns
- [ ] Module wiring check passes
- [ ] Circular dependency check passes
