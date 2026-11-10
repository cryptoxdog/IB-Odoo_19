---
auto_generated: false
authority: derived-index
component_id: plasticos_crm_bridge
component_name: PlastOS CRM Bridge
module_version: 19.0.3.4.24
layer: 3
installable: true
auto_install: true
application: false
depends:
  - crm
  - utm
  - plasticos_security_base
  - plasticos_web_leads
  - plasticos_matching
  - plasticos_offer
  - plasticos_material_profile
  - plasticos_facility_profile
  - plasticos_transaction
  - plasticos_logistics
  - plasticos_intake
models_owned:
  - plasticos.opportunity.approval
models_extended:
  - crm.lead
  - plasticos.web.lead
  - plasticos.material.profile
  - plasticos.facility.profile
  - plasticos.match.run
  - plasticos.offer
crons: []
---

# PlastOS CRM Bridge

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` win on any conflict. The manifest does not set `application`; Odoo's default is false.

## What it does

Makes the native `crm.lead` Opportunity the owner of a commercial pursuit. HOT web leads, manual Partner + Material Profile entry, and VanillaSoft contacts all end on one matching command, then on reviewed draft offers, then on one draft sale order for the accepted offer.

## How it works

1. **Opportunity.** A HOT `plasticos.web.lead` creates one `crm.lead` opportunity (`models/web_lead.py`, `_create_crm_lead`). It starts in the seeded non-won stage, unassigned, and creates no partner.
2. **Lot.** `crm.lead.action_approve_lot()` requires an opportunity with a linked Partner and Material Profile, then mints an immutable `plasticos.opportunity.approval` (`models/opportunity_approval.py`). The lot freezes the partner, material profile, optional facility profile, optional source intake, and a material `snapshot`. A later profile edit never rewrites it.
3. **Match.** `crm.lead.action_match_opportunity()` checks Gate availability with `classify_gate_availability`, approves the lot, commits it (`_plasticos_ensure_lot_durable`), then calls `plasticos.match.orchestrator.run_match_for_lot` with the snapshot. It creates no intake and no facility. Facility evidence is sent only when a facility profile is already linked. The commit keeps the lot when the orchestrator rolls back a failed run, so the failed run can be retried from the same lot.
4. **Offers.** `crm.lead.action_create_offers_from_results()` takes the accepted results of the latest successful run on the latest lot and creates one unsent draft `plasticos.offer` per result not already covered. It copies no price from the match; `quantity_lbs` comes from the lot snapshot. A unique index on `match_result_id` makes a second call create nothing.
5. **Acceptance.** The `plasticos.offer` extension (`models/match_lineage.py`) allows one accepted offer per opportunity, enforced by a partial unique index. `action_accept` then asks `sale.order._plasticos_draft_order_for_offer` (in `plasticos_transaction`) for one draft sale order bound to the opportunity. Confirming that order is left to the transaction compiler.

Lineage lives on the extended models: `plasticos.match.run.opportunity_id` and `approval_id`, `plasticos.offer.match_result_id` and `opportunity_id`.

Other extensions:

- `plasticos.facility.profile` (`models/facility_profile.py`): CRM ownership of a facility, linking a verified location, and merging a provisional facility onto an existing one.
- `plasticos.material.profile` (`models/material_profile.py`): match and transaction counts, profile reuse for a lead's facility.
- `crm.lead` (`models/crm_lead_vanillasoft.py`): `vanillasoft_id`, the VanillaSoft ContactID used to deduplicate imports.

Seed data: CRM stages, tags, partner categories, and lead sources under `data/`.

## Models

| Model                            | Kind     | File                                     |
| -------------------------------- | -------- | ---------------------------------------- |
| `plasticos.opportunity.approval` | owned    | `models/opportunity_approval.py`         |
| `crm.lead`                       | extended | `crm_lead.py`, `crm_lead_vanillasoft.py` |
| `plasticos.web.lead`             | extended | `models/web_lead.py`                     |
| `plasticos.material.profile`     | extended | `models/material_profile.py`             |
| `plasticos.facility.profile`     | extended | `models/facility_profile.py`             |
| `plasticos.match.run`            | extended | `models/match_lineage.py`                |
| `plasticos.offer`                | extended | `models/match_lineage.py`                |

`models/crm_tag_adoption.py` and `models/crm_mapping.py` hold helpers, not models.

## Runtime

- No cron.
- `auto_install` is true: Odoo installs it once every dependency is present.
- Gate matching needs `plasticos_gate` configured; `action_match_opportunity` refuses with a user error when Gate is unavailable.

## Boundaries

- It does not rank or score buyers. Matching runs through the one Gate orchestrator in `plasticos_matching`.
- It does not set prices, send offers, or confirm sale orders.
- It does not synthesize an intake or a facility for an opportunity.
- `plasticos_matching` does not depend on this module; this module depends on it.

## Read next

- [`models/crm_lead.py`](models/crm_lead.py)
- [`models/opportunity_approval.py`](models/opportunity_approval.py)
- [`models/match_lineage.py`](models/match_lineage.py)
- [`../plasticos_gate/README.md`](../plasticos_gate/README.md)
