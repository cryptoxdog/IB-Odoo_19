<!-- L9_META
skill_schema: 1
parent: plasticos-xml-view
layer: reference
role: ci_rules
tags: [plasticos, odoo19, xml, ci, validation]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Odoo 19 XML CI Rules

Authoritative detail: `.cursor/rules/84-ci-odoo19-patterns.mdc` and `AGENTS.md` CI Compliance Checklist.

## Rejected Patterns (selected)

| Pattern | Fix |
|---------|-----|
| `<tree>` | Use `<list>` |
| `attrs="{...}"` | Use `invisible=`, `readonly=`, `required=` |
| `states=` on fields | Use direct attribute expressions |
| `string=` on `<search>` | Remove |
| `string=` on search `<group>` | Remove |
| `decoration-secondary=` | Use supported decoration attrs |
| `t-esc=` | Use `t-out=` |
| Unescaped `&` | Use `&amp;` |
| Nested double quotes in `eval` | Single quotes inside eval |
| Cron `model_id` ref without module prefix | Add `plasticos_module.model_*` |
| `numbercall` on `ir.cron` | Remove (deprecated) |
| `category_id` on `res.groups` | Remove (Odoo 19) |

## Seed Data

- Wrap in `<odoo noupdate="1">`
- Deterministic external IDs with module prefix
- Load order via manifest `data` list

## Validation Commands

```bash
python3 ci/check_odoo19_xml.py
python3 ci/check_xpath_stability.py
xmllint --noout plasticos_*/**/*.xml
pre-commit run check-xml odoo19-xml xpath-stability --all-files
```

## eval Attribute

Use single quotes inside double-quoted eval:

```xml
eval="[ref('plasticos_base.partner_tag_buyer')]"
```

Not nested double quotes.
