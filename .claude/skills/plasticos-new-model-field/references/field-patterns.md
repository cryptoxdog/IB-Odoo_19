<!-- L9_META
skill_schema: 1
parent: plasticos-new-model-field
layer: reference
role: field_patterns
tags: [plasticos, odoo, field, orm, many2one, compute]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Field Patterns

## Adding a Field to Existing Model

1. Open model file in `plasticos_{module}/models/`
2. Add field:

```python
new_field = fields.Char(
    string="Human Label",
    help="Explain what this field stores and how it's used.",
    tracking=True,  # business-relevant fields
    index=True,     # search/filter fields
)
```

3. **Many2one** — model constant at top (`TARGET_MODEL = "plasticos.target"`), `domain=`, `ondelete="restrict"` or `"cascade"` explicitly.
4. **Selection** — module-level constant in same file; inline list acceptable.
5. **Compute** — `@api.depends()` with all actual dependencies; `store=True` when used in search/sort/group.
6. Update views in `views/`.
7. Write test in `tests/`.

## Computed Field Rules

- `@api.depends()` must list ALL field dependencies used in compute body.
- Never `@api.depends("id")` — crashes in Odoo 19.
- Run: `python3 ci/check_field_integrity.py`

## Anti-Patterns

- Hardcoded model strings on `fields.Many2one("plasticos.foo")` — use constant.
- String writes to Many2one fields — write record id.
- Top-level `from odoo.addons.plasticos_*` imports — lazy import inside functions only.
