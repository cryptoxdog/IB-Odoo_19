---
name: plasticos-xml-view
description: create or modify odoo 19 xml views following plasticos conventions. use when writing form, list, search, or xpath views; fixing odoo 19 view deprecations; or adding menu actions.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, xml, views, xpath, odoo19]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
---

# XML View Development

## Purpose

Create or extend Odoo 19 XML views in `plasticos_*` modules with CI-compliant patterns — list not tree, direct attributes not attrs, stable XPath anchors.

## Core Contract

| Element | Rule |
|---------|------|
| List views | `<list>` not `<tree>` |
| Search | No `string=` on `<search>` or search `<group>` |
| Visibility | `invisible=` / `readonly=` / `required=` — never `attrs=` or `states=` |
| XPath | Field-name anchors; run xpath stability check |
| Manifest | Every view XML listed in `__manifest__.py` `data` |

## Authority Order

1. Explicit user request (model, view type, inheritance target).
2. `AGENTS.md` — XML CI checklist (24 Odoo pattern checks).
3. `.cursor/rules/84-ci-odoo19-patterns.mdc`, `75-plasticos-xml-data-rules.mdc`.
4. Existing views in target module — match naming and external ID prefix.
5. This skill's references.
6. `Unknown` — stop if inherit view xml_id cannot be verified.

## Compact Workflow

1. Create or extend view file in `plasticos_{module}/views/`.
2. Apply patterns from [view-patterns.md](references/view-patterns.md).
3. Validate against [odoo19-xml-rules.md](references/odoo19-xml-rules.md).
4. Add to manifest `data`; run CI checks.

## Resource Map

- [references/view-patterns.md](references/view-patterns.md) — form, list, search templates, XPath extension.
- [references/odoo19-xml-rules.md](references/odoo19-xml-rules.md) — CI-rejected patterns and validation commands.

## Validation

```bash
python3 ci/check_odoo19_xml.py
python3 ci/check_xpath_stability.py
pre-commit run check-xml --all-files
```

All changed XML MUST pass odoo19-check before commit.

## Failure Handling

- `<tree>` in new view → replace with `<list>` before proceeding.
- Fragile XPath → refactor to `//field[@name='...']` anchor.
- `attrs=` in diff → convert to direct attributes per Odoo 19 rules.
- Unescaped `&` in XML → use `&amp;`; CI check #6 blocks merge.
