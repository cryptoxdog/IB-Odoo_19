---
auto_generated: false
authority: derived-index
component_id: plasticos_crm_bridge
component_name: PlastOS CRM Bridge
module_version: 19.0.3.6.3
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
  - sale_crm
  - plasticos_logistics
  - plasticos_intake
models_owned:
  - plasticos.opportunity.approval
  - plasticos.offer.buyer.selection.wizard
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

Makes the native `crm.lead` Opportunity the owner of a commercial pursuit. HOT web leads, manual Partner + Material Profile entry, and VanillaSoft contacts all reach buyers through one of two discovery paths, then on buyer-specific draft offers, an emailed offer, one accepted winner, and an admin release.

| Buyer discovery | Command | Offer lineage |
| --- | --- | --- |
| Gate matching | `action_match_opportunity` → review results → `action_create_offers_from_results` | `match_result_id` set; `opportunity_id` from the result's run |
| Manual selection | `action_select_offer_buyers` → **Select Buyers** dialog → Generate Draft Offers | `match_result_id` empty; `opportunity_id` and `material_source_id` set directly |

Both paths produce the same `plasticos.offer`; the manual path never calls Gate.

## How it works

1. **Opportunity.** A HOT `plasticos.web.lead` creates one `crm.lead` opportunity (`models/web_lead.py`, `_create_crm_lead`). It starts in the seeded non-won stage, unassigned, and creates no partner.
2. **Lot.** `crm.lead.action_approve_lot()` requires an opportunity with a linked Partner and Material Profile, then mints an immutable `plasticos.opportunity.approval` (`models/opportunity_approval.py`). The lot freezes the partner, material profile, optional facility profile, optional source intake, and a material `snapshot`. A later profile edit never rewrites it.
3. **Match.** `crm.lead.action_match_opportunity()` checks Gate availability with `classify_gate_availability`, approves the lot, commits it (`_plasticos_ensure_lot_durable`), then calls `plasticos.match.orchestrator.run_match_for_lot` with the snapshot. It creates no intake and no facility. Facility evidence is sent only when a facility profile is already linked. The commit keeps the lot when the orchestrator rolls back a failed run, so the failed run can be retried from the same lot.
4. **Offers.** `crm.lead.action_create_offers_from_results()` takes the accepted results of the latest successful run on the latest lot and creates one unsent draft `plasticos.offer` per result not already covered. It copies no price from the match; `quantity_lbs` comes from the lot snapshot. A unique index on `match_result_id` makes a second call create nothing.
5. **Manual offers.** `crm.lead.action_select_offer_buyers()` validates an open opportunity with a supplier and its own material row (`plasticos.opportunity.material`), then opens `plasticos.offer.buyer.selection.wizard` (`wizards/offer_buyer_selection_wizard.py`). The broker selects existing Contacts with the native Contacts search. On **Generate Draft Offers** the server re-checks access, active state, company scope and the supplier, groups the contacts by `commercial_partner_id`, and creates or reuses one Draft offer per buyer company with the selected contacts (those with an email) as `recipient_partner_ids`. The draft takes quantity from the material row, one load, no price (the supplier `buy_price_per_lb` is never copied), a buyer-facing `material_description`, and references the row's pictures without copying them. A second Draft for the same opportunity and buyer is refused by a partial unique index; a sent offer is history and a new proposal is a new draft.
6. **Send.** Sending is owned by `plasticos_offer`: Send Offer opens the native email composer and the offer becomes Sent only after Odoo Mail accepts the email. For a manual offer the specification of its material row is frozen in `material_spec_key` at that moment.
7. **Acceptance.** The `plasticos.offer` extension (`models/match_lineage.py`) allows one accepted offer per opportunity, Gate or manual, enforced by a partial unique index, and moves the opportunity to the native Won stage. It creates no order.
8. **Release.** `crm.lead.action_submit_release()` (Operations Manager) creates one draft purchase order, one draft sale order and one draft transaction for the accepted offer. The purchase order is priced at the opportunity's supplier Offer Price (`buy_price_per_lb` on its material row) as it stands at submit; that price stays editable on the opportunity, Won included, so it can carry the final agreement. Submit refuses a missing price. The accepted offer's `price_per_lb` is the buyer-facing price and never prices the purchase. For a manual offer, submit also refuses, before creating anything, a release buyer company other than the offer's buyer, a facility outside that buyer, or a buyer price that differs from the accepted `price_per_lb` (compared at four decimals, the finer of the currency's and the stored per-lb precision).
9. **History.** A manual offer must be really sent before it can be accepted, and once emailed it never returns to Draft, through Reset to Draft or a raw write. Its email, recipients, pictures and terms stay as sent; a revised proposal is a new offer from Select Buyers. For a manual offer it first refuses when the opportunity's material row is not the one the offer was sent for, or its specification changed after sending.

Lineage lives on the extended models: `plasticos.match.run.opportunity_id` and `approval_id`, `plasticos.offer.match_result_id`, `opportunity_id`, `material_source_id` and `material_spec_key`. `plasticos.offer.opportunity_id` is one stored relation (the same column as the former related field), filled from the result for a Gate offer and set directly for a manual one.

Other extensions:

- `plasticos.facility.profile` (`models/facility_profile.py`): CRM ownership of a facility, linking a verified location, and merging a provisional facility onto an existing one.
- `plasticos.material.profile` (`models/material_profile.py`): match and transaction counts, profile reuse for a lead's facility.
- `crm.lead` (`models/crm_lead_vanillasoft.py`): `vanillasoft_id`, the VanillaSoft ContactID used to deduplicate imports.

Seed data: CRM stages, tags, partner categories, and lead sources under `data/`.

## Models

| Model                            | Kind     | File                                     |
| -------------------------------- | -------- | ---------------------------------------- |
| `plasticos.opportunity.approval` | owned    | `models/opportunity_approval.py`         |
| `plasticos.offer.buyer.selection.wizard` | owned, transient | `wizards/offer_buyer_selection_wizard.py` |
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
- It does not set prices, send email, or confirm sale orders. Email sending is `plasticos_offer`'s Send Offer.
- Manual buyer selection creates no contact and invents no email address.
- It does not synthesize an intake or a facility for an opportunity.
- `plasticos_matching` does not depend on this module; this module depends on it.

## Read next

- [`models/crm_lead.py`](models/crm_lead.py)
- [`models/opportunity_approval.py`](models/opportunity_approval.py)
- [`models/match_lineage.py`](models/match_lineage.py)
- [`../plasticos_gate/README.md`](../plasticos_gate/README.md)
