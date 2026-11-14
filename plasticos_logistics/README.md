---
auto_generated: false
authority: derived-index
component_id: plasticos_logistics
component_name: Plasticos Logistics Engine
module_version: 19.0.1.14.26
layer: 5
installable: true
auto_install: true
application: true
depends:
  - plasticos_base
  - plasticos_transaction
  - sale_management
  - stock
  - purchase
  - purchase_stock
  - mail
  - base_automation
models_owned:
  - plasticos.load
  - plasticos.dispatch
  - plasticos.load.dashboard
  - plasticos.freight.quote.request
  - plasticos.freight.quote.recipient
  - plasticos.freight.quote
  - plasticos.freight.estimate
  - plasticos.freight.event
  - plasticos.freight.calibration.observation
  - plasticos.rate.memory
  - plasticos.rate.memory.reconciliation
  - plasticos.logistics.request
  - plasticos.logistics.response
  - plasticos.freight.actual.correction.wizard
  - plasticos.load.bulk.update.wizard
models_extended:
  - plasticos.transaction
  - sale.order
  - purchase.order
  - mail.mail
crons:
  - cron_escalation
  - cron_dispatch_acknowledgment
  - cron_supplier_confirmation
  - cron_auto_create_do
---

# Plasticos Logistics Engine

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` and `wizards/` win on any conflict.

## Business requirements and implementation plan

Linda's seven original BRS files (60 rule IDs) are in [`business_rules/`](business_rules/README.md), governed by the exact-ID [`SUPERSESSION.md`](business_rules/SUPERSESSION.md) and bound to WP00-WP11 and planned acceptance by [`LINDA_BUILD_PLAN.md`](LINDA_BUILD_PLAN.md). This is a target specification, not a runtime-completion claim.

Read [`AGENTS.md`](AGENTS.md) before changing Linda code. It requires BRS rule IDs in changes and tests and forbids unauthorized live sends.

## What it does

Moves material from supplier to buyer: loads, readiness, rates, scheduling, dispatch, pickup, delivery, and close. It holds Odoo-local freight evidence (Same As Last resolution, manual-only quote requests, nonbinding estimates, calibration observations) and Linda's order-scoped supplier and buyer mail records.

## How it works

- **Load.** `plasticos.load` (`models/load.py`) is the unit of work. `state` runs `draft`, `awaiting_ready`, `ready_confirmed`, `rate_confirmed`, `scheduled`, `dispatched`, `picked_up`, `delivered`, `closed`, with `exception` beside them. Main commands: `action_confirm_ready`, `action_confirm_rate`, `action_schedule`, `action_dispatch`, `action_close`.
- **Freight.**
  - `action_resolve_freight` resolves Same As Last from executed-load history (`services/sal_resolver.py`). A miss never creates a quote request by itself.
  - `action_create_freight_quote_request` opens one manual-only request (`plasticos.freight.quote.request`, its recipients and quotes).
  - `action_request_freight_estimate` stores a nonbinding `plasticos.freight.estimate`. The math is `services/freight_estimation.py`: a Haversine-weighted curve over canonical executed lanes. That file reads and writes no model; `services/freight_history.py` supplies the evidence and the load writes the rows.
  - `action_record_actual_freight_cost` and `action_correct_actual_freight_cost` append `plasticos.freight.calibration.observation` rows. Corrections do not reopen earlier evidence.
  - `plasticos.freight.event` records freight decisions. `plasticos.rate.memory` is frozen: create and write raise outside its migration context. `plasticos.rate.memory.reconciliation` records its reconciliation.
- **Dispatch documents.** `report/` defines BOL pickup, BOL delivery, delivery order, and a supplier purchase order report. `action_send_dispatch_packet` opens a composer; `action_send_dispatch_direct` sends the packet at once. Both use the `email_template_dispatch_packet` template from `plasticos_automation` and raise a clear error when that module is not installed.
- **Linda order mail.** Approving a purchase order (`button_approve`) or confirming a sale order (`action_confirm`) records a `plasticos.logistics.request` when the order newly enters `purchase` or `sale`. Cancels record cancel requests.
  - The system parameter `plasticos_logistics.linda_mode` is `off`, `shadow`, or `live`. Anything else is treated as `off`, and no value is seeded, so a fresh install records nothing.
  - `shadow` records evidence and creates no mail. Only `live` queues mail through the native template.
  - A request becomes `sent` only after Odoo Mail reports the `mail.mail` as sent; an unrecorded outcome becomes `unknown` and is not retried automatically.
  - The `mail.mail` extension rechecks queued Linda mail at send time, sends it one at a time, and holds an issue mail until an earlier cancellation to the same party is confirmed sent.
- **Linda typed obligations (S4).** The same request owner records booking issue/amend/cancel, dispatch acknowledgement reminder (+2h) and escalation (+4h, carrier and ops), and carrier document chase. Each has a `source_kind`, an accepted `source_revision_key`, one audience and an immutable snapshot that its template on `plasticos.logistics.request` renders. Booking mail goes only through `request_booking_correspondence`; its source resolver is registered by `plasticos_export`, and without it the answer is `not_available`. The acknowledgement job polls every five minutes from the actual `dispatch_sent` time and never reattaches the packet. A document chase reads the Documents scale-ticket status, runs only when `plasticos_logistics.linda_document_chase` is `1`, and is withheld once the ticket is received.
  - The native send claim locks the source row, then the request row, and re-reads the source before SMTP. A revision that wins first withholds the old mail; a claim that wins first is kept as history, and the later revision is held. Unknown outcomes are never resent.
  - A carrier dispatch or document composer re-checks the physical-release guard when it sends, not only when it opens, and cannot be scheduled.
- **Linda replies.** `plasticos.logistics.response` records which request an incoming message answers, proven by `In-Reply-To` / `References`. Only exact standard replies ("confirmed", "confirm", "not ready") are classified; free-form replies stay unresolved. It changes no order, load, picking, or transaction. `data/linda_inbound_ai.xml` wires it to new `mail.message` records.
- **Road equipment (S9).** `plasticos.road.equipment.type` is the one domestic trailer catalog: 53 ft trailer, 48 ft trailer and flatbed are seeded (`data/road_equipment_type_data.xml`); more are added as data. A load names it in `road_equipment_type_id` and states the actual dimensions in `road_equipment_requirements`. A flatbed has no assumed length. No payload, VGM or container is inferred from it (BRS-EXP-07-R002).
- **Container journey facts (S9).** A J1 `plasticos.iso.journey` stays identity only. `plasticos.iso.journey.fact` (`models/iso_journey_fact.py`) records what later happened to it, one immutable row per kind: terminal `gate_in`, vessel `departure` (after its gate-in), `regulatory_parties` (customs filer, delivery partner), `container_tare` and `verified_gross_mass` (a weight and a weight unit from a scale ticket, or for VGM only from the Documents `verified_gross_mass` verdict; BRS-EXP-07-R006). Only Logistics, Operations Manager and System can read them. Only `action_record_gate_in`, `action_record_departure`, `action_record_regulatory_parties`, `action_record_container_tare` and `action_record_verified_gross_mass` write them, from an original attached to the journey. A later buyer, sale order or resale cannot rewrite them (BRS-EXP-08-R007, BRS-EXP-10-R007).
- **Shipment event proposals (S9).** `plasticos.shipment.event.proposal` is a reviewable candidate that one shipment event happened: `supplier_ready` or `loaded` for a load, `gate_accepted` or `sailed` for a journey. Proposing writes nothing else. Accept runs the owner command (`action_confirm_ready`, `action_record_actual_event('pickup')`, `plasticos.iso.journey.fact.action_record_gate_in` / `action_record_departure`) with its own guards. A supplier report cannot attest gate-in or a sailing. A cited Linda reply speaks only for the recipient of the request it answers: the supplier role wins (pickup party, transaction supplier or PO vendor), otherwise the load's road carrier; a Linda reply never supports `gate_accepted` or `sailed` (BRS-EXP-09-R007, BRS-EXP-11-R010). Commands return `{status, record_id?, reason?}` with status `applied`, `already_applied`, `blocked`, `not_available`, or `rejected` (a proposal key replayed after rejection).
- **Journey-fact corrections (S11).** `plasticos.iso.journey.fact.action_correct_fact(fact_id, values, correction_reason, operation_key)` records revision `n + 1` of a fact: it names the revision it supersedes and stores the required reason, author, time and operation key. The superseded row is never written. The correction runs every guard of the first record, and an empty reason, an unchanged value, a stale revision or a reused key is refused. The current fact of each kind is its highest revision, read through `plasticos.iso.journey.current_facts()` and `current_fact(kind)` with the caller's rights. Migration 19.0.1.14.24 sets revision 1 on facts recorded before it (BRS-EXP-08-R007, operator decision 2026-11-12).
- **Linda sweep cursor (S11).** The load-obligation sweep keeps its page cursor in `plasticos.linda.sweep.cursor`, one row per lane (`ack`, `chase`) and company (company record rule), and no longer writes `ir.config_parameter`. The sweep reads and writes the row of the company it runs in. Migration 19.0.1.14.24 moved the single global parameter value of each lane once into the row of the sweep company (the `plasticos_base.user_system_cron` company, else the main company) and removed the parameter; other companies start their cursor at 0.
- **Linda approvals (S11).** Linda is `user_linda` (`data/linda_user.xml`, updatable), a service user without a password who holds the Logistics group only (granted by `plasticos_security_base`). When she corrects a journey fact, proposes from an unverified Linda reply, accepts a proposal, confirms a load ready, corrects a recorded actual pickup or delivery, records a journey fact or actual event that conflicts, is out of sequence, has a unit mismatch or lacks verified evidence, or calls a command again on a subject where her last call was refused, the command returns `{status: "pending", approval_id, reason}` and waits in `plasticos.linda.approval` (`models/linda_approval.py`, menu Linda Approvals). Her refusals are recorded there too (state `refused`). An Operations Manager approves (the command runs as Linda in the approval's company) or rejects it; Linda and other Logistics users cannot. An approved value conflict is refused as stale when the fact it conflicted with was corrected meanwhile. Linda creates proposals only through `action_propose_shipment_event`. Her straight-through outcomes and every person's commands apply at once. No cron runs as her. Archiving her is the operator's stop and pauses her: every gated command answers `blocked` and writes nothing, the sweep stops and her queued mail is withheld until she is reactivated, while her mode is unchanged, so she keeps owning order issuance, obligations still queue and replies are still recorded; no upgrade reactivates her. She cannot set a load's state, readiness stamp or actual events by a raw write.
- **Dashboard.** `plasticos.load.dashboard` is a read-only SQL view, one row per non-cancelled load.
- **Extensions.** `plasticos.transaction` gets `load_ids`, `load_count`, and `action_view_loads`. `sale.order` gets `action_create_load`. Both order models get `linda_request_ids`.
- **Install hook.** `post_init_hook` in `hooks.py` grants this module's groups to the users of the crons it owns.

## Models

| Model                                        | Kind             | File                                          |
| -------------------------------------------- | ---------------- | --------------------------------------------- |
| `plasticos.load`                             | owned            | `models/load.py`                              |
| `plasticos.dispatch`                         | owned            | `models/dispatch.py`                          |
| `plasticos.load.dashboard`                   | owned, SQL view  | `models/load_dashboard.py`                    |
| `plasticos.freight.quote.request`            | owned            | `models/freight_quote.py`                     |
| `plasticos.freight.quote.recipient`          | owned            | `models/freight_quote.py`                     |
| `plasticos.freight.quote`                    | owned            | `models/freight_quote.py`                     |
| `plasticos.freight.estimate`                 | owned            | `models/freight_estimate.py`                  |
| `plasticos.freight.event`                    | owned            | `models/freight_governance.py`                |
| `plasticos.freight.calibration.observation`  | owned            | `models/freight_governance.py`                |
| `plasticos.rate.memory`                      | owned, frozen    | `models/rate_memory.py`                       |
| `plasticos.rate.memory.reconciliation`       | owned            | `models/freight_governance.py`                |
| `plasticos.logistics.request`                | owned            | `models/linda_request.py`                     |
| `plasticos.logistics.response`               | owned            | `models/linda_response.py`                    |
| `plasticos.iso.journey`                      | owned            | `models/iso_journey.py`                       |
| `plasticos.iso.journey.source`               | owned            | `models/iso_journey.py`                       |
| `plasticos.iso.journey.fact`                 | owned            | `models/iso_journey_fact.py`                  |
| `plasticos.road.equipment.type`              | owned            | `models/road_equipment.py`                    |
| `plasticos.shipment.event.proposal`          | owned            | `models/shipment_event_proposal.py`           |
| `plasticos.linda.sweep.cursor`               | owned            | `models/linda_sweep_cursor.py`                |
| `plasticos.linda.approval`                   | owned            | `models/linda_approval.py`                    |
| `plasticos.freight.actual.correction.wizard` | owned, transient | `wizards/freight_actual_correction_wizard.py` |
| `plasticos.load.bulk.update.wizard`          | owned, transient | `wizards/load_bulk_update_wizard.py`          |
| `plasticos.transaction`                      | extended         | `models/transaction_inherit.py`               |
| `sale.order`                                 | extended         | `models/sale_order_inherit.py`                |
| `purchase.order`                             | extended         | `models/purchase_order_inherit.py`            |
| `mail.mail`                                  | extended         | `models/mail_mail_inherit.py`                 |

## Runtime

All four crons are in `data/cron.xml` (`noupdate="0"`) and run as `plasticos_base.user_system_cron`:

| Cron                           | Calls                                                          | Interval | `active` in XML |
| ------------------------------ | -------------------------------------------------------------- | -------- | --------------- |
| `cron_escalation`              | `plasticos.load._cron_escalation_check()`                      | 1 hour   | not set         |
| `cron_dispatch_acknowledgment` | `plasticos.load._cron_check_dispatch_acknowledgments()`        | 4 hours  | true            |
| `cron_supplier_confirmation`   | `plasticos.transaction._cron_supplier_confirmation_followup()` | 6 hours  | true            |
| `cron_auto_create_do`          | `plasticos.transaction._cron_auto_create_delivery_orders()`    | 1 hour   | true            |

The two transaction methods are defined in `plasticos_transaction`, not here.

`auto_install` and `application` are true.

## Boundaries

- No Gate, CEG, enrichment engine, LLM, or external pricing service. Freight estimation is local math.
- Linda sends external mail only through native Odoo Mail, only in `live` mode. Installing this module or its BRS pack does not turn on live sends.
- Freight estimates are nonbinding. No carrier is awarded automatically.
- Registered BRS requirements are not evidence that the behaviour is implemented or validated at runtime.

## Read next

- [`AGENTS.md`](AGENTS.md)
- [`LINDA_BUILD_PLAN.md`](LINDA_BUILD_PLAN.md)
- [`business_rules/README.md`](business_rules/README.md)
- [`models/load.py`](models/load.py)
- [`models/linda_request.py`](models/linda_request.py)
