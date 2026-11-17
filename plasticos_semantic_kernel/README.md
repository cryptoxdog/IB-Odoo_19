---
auto_generated: false
authority: derived-index
component_id: plasticos_semantic_kernel
component_name: PlasticOS Semantic Kernel
module_version: 19.0.1.0.6
installable: true
auto_install: false
application: false
depends:
  - mail
  - plasticos_material_profile
  - plasticos_facility_profile
  - plasticos_intake
  - plasticos_crm_sync
models_owned:
  - plasticos.material.specification
  - plasticos.material.observation
  - plasticos.supply.opportunity
  - plasticos.buyer.demand
  - plasticos.facility.material.rule
  - plasticos.capacity.observation
models_extended: []
crons: []
---

# PlasticOS Semantic Kernel

The front matter above is a derived index. `__manifest__.py` and the `_name` lines in `models/` win on any conflict. `AGENTS.md` gives this module no layer, so none is recorded here.

## What it does

Adds semantic models that describe material requirements, observed material values, supply and demand candidates, and facility capability rules. `auto_install` is false and `AGENTS.md` says it stays uninstalled. No module depends on it; do not add it to any `depends` list.

## How it works

Six models, each with its own views under `views/` and a menu in `views/menus.xml`:

- **`plasticos.material.specification`**: versioned normative requirements for a material (polymer, form, color, source type, filler), optionally tied to a material profile.
- **`plasticos.material.observation`**: an attributed measured, reported, or inferred value against a material profile or specification.
- **`plasticos.supply.opportunity`**: an active supply candidate from a supplier, linked to a material profile, a specification, and optionally an intake.
- **`plasticos.buyer.demand`**: a qualified buyer requirement against a specification.
- **`plasticos.facility.material.rule`**: whether a facility profile accepts, rejects, prefers, or requires a material (polymer, form, source type, filler, equipment).
- **`plasticos.capacity.observation`**: an attributed capacity measurement for a facility profile.

Supply opportunities and buyer demands are records in these tables. They are not `crm.lead`, and they are not the commercial pursuit; the CRM Opportunity in `plasticos_crm_bridge` is.

## Models

| Model                              | Kind  | File                               |
| ---------------------------------- | ----- | ---------------------------------- |
| `plasticos.material.specification` | owned | `models/material_specification.py` |
| `plasticos.material.observation`   | owned | `models/material_observation.py`   |
| `plasticos.supply.opportunity`     | owned | `models/supply_opportunity.py`     |
| `plasticos.buyer.demand`           | owned | `models/buyer_demand.py`           |
| `plasticos.facility.material.rule` | owned | `models/facility_material_rule.py` |
| `plasticos.capacity.observation`   | owned | `models/capacity_observation.py`   |

## Runtime

- No cron, no install hook, no seed data.
- `installable` is true; `auto_install` and `application` are false.
- Two offline scripts at the repository root work with these models. Installing or upgrading the module does not run them.
  - `scripts/semantic_kernel_backfill.py` is an explicit backfill CLI (with `scripts/semantic_kernel_backfill_engine.py`). Its docstring says only the specification family runs; supply and demand report blocked.
  - `scripts/opportunity_protocol.py` holds runtime validators for the supply-opportunity and buyer-demand payloads described under `contracts/schemas/`.

## Boundaries

- No Gate client, no scoring, no inference.
- No module depends on it, and it is not part of the commercial flow.

## Read next

- [`models/supply_opportunity.py`](models/supply_opportunity.py)
- [`models/facility_material_rule.py`](models/facility_material_rule.py)
- [`../scripts/semantic_kernel_backfill.py`](../scripts/semantic_kernel_backfill.py)
