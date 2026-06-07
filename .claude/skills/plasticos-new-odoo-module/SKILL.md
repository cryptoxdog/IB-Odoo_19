---
name: plasticos-new-odoo-module
description: create a new plasticos odoo 19 module with proper structure, manifest, acl, views, and layer-correct dependencies. use when scaffolding a new plasticos_* addon or bootstrapping module files.
skill_schema: 1
layer: control_plane
role: skill_entrypoint
tags: [plasticos, odoo, module, scaffold, layer, manifest]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
---

# New Odoo Module

## Purpose

Scaffold a new `plasticos_*` Odoo 19 addon with correct layer placement, manifest contract, ACL, views, seed data, and install order.

## Core Contract

| Artifact | Requirement |
|----------|-------------|
| Directory | `plasticos_{name}/` with non-empty root `__init__.py` |
| Manifest | Version `19.0.X.Y.Z`, layer-correct `depends`, all data files listed |
| Models | `_name` literal, string constants, `Plasticos*` class prefix |
| Security | `ir.model.access.csv` for every new model |
| Install order | Entry in `config/odoo_module_order.yaml` |

## Authority Order

1. Explicit user approval — new modules affect dependency graph (master context: ask before creating).
2. `ARCHITECTURE.md` — layer 1–5 placement and dependency direction.
3. `INVARIANTS.md` — no circular deps, deterministic seed doctrine.
4. `AGENTS.md` — new Python file, new model, manifest CI rules.
5. `.cursor/rules/81-ci-manifest-contract.mdc`, `82-ci-module-wiring.mdc`.
6. This skill's references.
7. `Unknown` — stop if layer or depends list cannot be verified.

## Compact Workflow

1. Determine layer per [layer-depends.md](references/layer-depends.md).
2. Scaffold per [scaffold-checklist.md](references/scaffold-checklist.md).
3. Run wiring and circular-dep checks.
4. Register in `config/odoo_module_order.yaml`.

## Resource Map

- [references/scaffold-checklist.md](references/scaffold-checklist.md) — directory layout, manifest, models, security, views, data.
- [references/layer-depends.md](references/layer-depends.md) — layer map and dependency rules.

## Validation

```bash
python3 scripts/check_module_wiring.py
python3 ci/check_circular_deps.py
pre-commit run --all-files
```

All checklist items in scaffold-checklist MUST be satisfied before declaring complete.

## Failure Handling

- Circular dependency detected → revise `depends` or defer module; do not merge with cycle.
- Cross-layer import → use Integer FK or move model to correct layer.
- Missing ACL → add before any model merge; CI blocks registry load.
- User has not approved new module → STOP at step 1.
