---
name: new-field
description: Add a new field or model to an existing PlasticOS module
---

# New Model / Field

## Adding a Field to Existing Model

1. Open the model file in `plasticos_{module}/models/`
2. Add field following this pattern:
   ```python
   new_field = fields.{Type}(
       string="Human Label",
       help="Explain what this field stores and how it's used.",
       tracking=True,  # for business-relevant fields
       index=True,     # for fields used in search/filter
   )
   ```
3. If the field is a `Many2one`, add:
   - Model string constant at top: `TARGET_MODEL = "plasticos.target"`
   - `domain=` for filtering
   - `ondelete="restrict"` or `"cascade"` explicitly
4. If the field is a `Selection`, define choices as module-level constant
5. If `compute=`, declare `@api.depends()` with all actual dependencies
6. Update views in `views/` to display the new field
7. Update `security/ir.model.access.csv` if new model
8. Write a test in `tests/` verifying the field behavior
9. Run `pre-commit run --all-files`

## Adding a New Model

1. Create model file in `plasticos_{module}/models/{model_name}.py`
2. Import in `models/__init__.py`
3. Follow naming: `_name = "plasticos.{model_name}"`
4. Add `_description`, inherit `mail.thread` for business models
5. Create `security/ir.model.access.csv` entry
6. Create views (form + tree + search minimum)
7. Add menu item in `views/menu.xml`
8. Write tests

## Computed Field Rules
- `@api.depends()` must list ALL actual field dependencies
- ❌ Never use `@api.depends("id")` — crashes in Odoo 19
- Use `store=True` for fields used in search/sort/group
- Run: `python3 ci/check_field_integrity.py`
