---
auto_generated: false
authority: derived-index
component_id: plasticos_offer
component_name: PlasticOS Offer
module_version: 19.0.1.2.0
layer: 3
installable: true
auto_install: true
application: false
depends:
  - plasticos_base
  - base
  - mail
  - plasticos_intake
models_owned:
  - plasticos.offer
  - plasticos.offer.bulk.action.wizard
models_extended:
  - plasticos.intake
  - plasticos.offer
crons:
  - ir_cron_expire_offers
---

# PlasticOS Offer

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` and `wizards/` win on any conflict.

## What it does

Holds one commercial offer from a supplier to a buyer and its lifecycle from draft to accepted, rejected, expired, or cancelled.

## How it works

- **Offer.** `plasticos.offer` (`models/offer.py`) names the parties `supplier_id` and `buyer_id`, an optional `intake_id`, and the terms: `price_per_lb`, `currency_id`, `quantity_lbs`, `loads`, delivery and payment terms, and `valid_until`. The reference comes from the `plasticos.offer` sequence on create. When the offer has an intake, its images are copied from the intake.
- **States.** `draft`, `sent`, `responded`, `accepted`, `rejected`, `expired`, `cancelled`.
  - `action_send` moves a draft to `sent`.
  - `action_mark_responded` moves `sent` to `responded`.
  - `action_accept` accepts a `sent` or `responded` offer and records who accepted it and when.
  - `action_reject`, `action_cancel`, and `action_reset_to_draft` cover the rest.
- **Frozen terms.** Once an offer leaves draft, a write that changes a term field (price, currency, quantity, loads, delivery and payment terms, validity, parties, intake) is refused. For an `accepted`, `rejected`, `expired`, or `cancelled` offer, a write without `state` is refused. A write that includes `state` skips that check, so it can still change non-term fields on a closed offer; only the term-field check applies to it. A changed deal is a new offer.
- **Expiry.** Cron `ir_cron_expire_offers` calls `cron_expire_offers()` daily. It takes the advisory lock `plasticos_offer.ir_cron_expire_offers` and moves up to 500 `draft`, `sent`, or `responded` offers past `valid_until` to `expired`.
- **Two creation paths, one price rule.** `models/offer_price_bridge.py` fills `price_per_lb` on create from the highest `plasticos.intake.match.typical_price` for that intake and buyer, and only when the new offer has an intake and a buyer, no `match_result_id`, and no price yet.
  - A manually entered intake offer gets that typical price as a starting value.
  - An offer created from a reviewed Gate match result carries `match_result_id` (a field owned by `plasticos_crm_bridge`) and is left untouched. Its terms are the broker's.
- **Intake side.** The `plasticos.intake` extension (`models/intake_offers_bridge.py`) adds `offer_ids`, `offer_count`, and `action_view_offers`. Its `action_send_offers` is retired: it raises a user error that points at the Opportunity and creates no offer.
- **Bulk actions.** `plasticos.offer.bulk.action.wizard` sends, accepts, rejects, or cancels many offers at once.
- **Install hook.** `post_init_hook` in `hooks.py` grants this module's groups to the users of the crons it owns.

## Models

| Model                                | Kind             | File                                  |
| ------------------------------------ | ---------------- | ------------------------------------- |
| `plasticos.offer`                    | owned            | `models/offer.py`                     |
| `plasticos.offer.bulk.action.wizard` | owned, transient | `wizards/offer_bulk_action_wizard.py` |
| `plasticos.intake`                   | extended         | `models/intake_offers_bridge.py`      |
| `plasticos.offer`                    | extended         | `models/offer_price_bridge.py`        |

## Runtime

- Cron: `ir_cron_expire_offers`, daily, `active` true in `data/offer_cron.xml`.
- `auto_install` is true.

## Boundaries

- It sends no email by itself and calls no external service. `sent` is a state, not a delivery. `action_email_images` only opens the mail composer with the material images attached.
- It does not create offers from match results. `plasticos_crm_bridge.crm.lead.action_create_offers_from_results` does, and it also owns `match_result_id`, `opportunity_id`, and the one-winner-per-opportunity rule.
- It does not create a sale order or a transaction on acceptance.

## Read next

- [`models/offer.py`](models/offer.py)
- [`models/offer_price_bridge.py`](models/offer_price_bridge.py)
- [`../plasticos_crm_bridge/README.md`](../plasticos_crm_bridge/README.md)
