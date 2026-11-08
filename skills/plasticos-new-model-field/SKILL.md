---
name: plasticos-new-model-field
description: add a new field or model to an existing plasticos module. use when adding fields, many2one relations, selection values, computed fields, or new models within an existing plasticos_* addon.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, field, model, acl, views]
owner: igor_beylin
status: active
disable-model-invocation: false
version: 1.1.0
updated: 2026-06-06
---

# New Model / Field

## Purpose

Add a field or model to an existing `plasticos_*` module with correct Odoo 19 ORM patterns, manifest deps, ACL, views, and tests.

## Core Contract

| Operation | Required artifacts |
|-----------|-------------------|
| New field on existing model | Field declaration, view update, test, `pre-commit` |
| New model in existing module | Model file, `__init__.py` import, ACL, views, menu, test |
| Many2one | Model constant, `domain=`, `ondelete=` explicit |
| Selection | Inline list or same-file constant (phantom-enum CI) |
| Compute | `@api.depends()` with all real deps; never `@api.depends("id")` |

## Authority Order

1. Explicit user request (model, module, field spec).
2. `INVARIANTS.md` — `_name` literal, Many2one `ondelete`, no `_sql_constraints`.
3. `AGENTS.md` — CI Compliance Checklist (new model/field/file rules).
4. `.cursor/rules/82-ci-module-wiring.mdc`, `83-ci-phantom-enum.mdc`, `71-plasticos-security-model.mdc`.
5. This skill's references.
6. `Unknown` — stop if comodel module or layer boundary is unclear.

## Compact Workflow

1. Read target model file and full ACL CSV before editing.
2. Apply patterns from [field-patterns.md](references/field-patterns.md).
3. Wire views, manifest deps, and ACL per [new-model-checklist.md](references/new-model-checklist.md).
4. Write at least one test; run validation commands.

## Resource Map

- [references/field-patterns.md](references/field-patterns.md) — field, Many2one, Selection, compute patterns.
- [references/new-model-checklist.md](references/new-model-checklist.md) — new model wiring, ACL, views, validation commands.

## Validation

Before declaring complete:

```bash
python3 ci/check_field_integrity.py
python3 scripts/check_module_wiring.py
pre-commit run --all-files
```

New models MUST have ACL rows in the same module. Cross-module `comodel_name` MUST appear in `__manifest__.py` `depends`.

## Failure Handling

- ACL CSV edit without reading current file → STOP; `cat` full CSV first per master context.
- Phantom enum CI failure → add inline Selection constant or GLOBAL_ALLOWLIST entry; do not skip test.
- Cross-layer Many2one prohibited → use `Integer` FK per wiring rule 82.
- Missing manifest dep → add to `depends` before import; re-run wiring check.
