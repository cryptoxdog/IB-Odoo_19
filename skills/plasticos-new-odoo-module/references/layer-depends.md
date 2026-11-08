<!-- L9_META
skill_schema: 1
parent: plasticos-new-odoo-module
layer: reference
role: architecture_contract
tags: [plasticos, odoo, layer, depends, architecture]
owner: igor_beylin
status: active
version: 1.1.0
updated: 2026-06-06
/L9_META -->

# Layer and Dependency Rules

Per `ARCHITECTURE.md` — higher layers depend on lower; never reverse.

## Layer Map (abbreviated)

| Layer | Modules (examples) |
|-------|-------------------|
| 1 Material | `plasticos_base`, `plasticos_material_profile`, `plasticos_product` |
| 2 Capability | `plasticos_intake`, `plasticos_matching`, `plasticos_buyer_match_engine` |
| 3 Commercial | `plasticos_offer`, `plasticos_commission`, `plasticos_accounting` |
| 4 Compliance | `plasticos_documents`, `plasticos_documents_native` |
| 5 Transaction | `plasticos_transaction`, `plasticos_logistics`, `plasticos_claims` |

## Rules

- New module MUST declare `depends` only on same or lower layers.
- Cross-layer Many2one where prohibited → use `Integer` FK (see `82-ci-module-wiring`).
- Pre-existing non-fatal cycle: `commission ↔ transaction` — do not add new cycles.
- Seed data: XML with `noupdate="1"`; no CSV runtime bootstrap.

## Determine Layer Before Scaffold

1. Read `ARCHITECTURE.md` module table.
2. Identify primary business concern (material, intake/match, offer, docs, transaction).
3. List upstream modules the new code will import or reference.
4. Verify no upstream module depends on the new module.
