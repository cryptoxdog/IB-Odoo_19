# ADR-135 Dock rules, appointments and the soonest full-weight schedule

- Status: Accepted (operator, 2026-11-17).
- Decision date: 2026-11-17
- Owners: `plasticos_logistics`, `plasticos_transaction`, `plasticos_automation`, `plasticos_commission`, `plasticos_crm_bridge` (order and dashboard fields); `plasticos_facility_profile` (site fields, ADR-134 §4)
- Implements: LINDA_BUILD_PLAN WP04 (appointments) and the readiness half of WP03
- Rules: BRS-02-R004, BRS-02-R005; BRS-03-R016, R017, R018, R019, R020, R021, R022
- Introduces: POS-INV-21 and a SUPERSESSION entry
- Relates to: ADR-131 (sites), ADR-134 (site logistics fields), ADR-130 and BRS-EXP-02 (export booking and cutoff), BRS-04 (Linda has no rate authority), S11 (Linda approval gate)

## Context (verified on Staging 42db406)

**One dock rule is used for both sides.**
- The transaction holds a single `delivery_term` (`plasticos_transaction/models/transaction.py:161`). It defaults to the supplier partner's `default_delivery_term`, then the buyer's (`:523`).
- Every partner defaults to Appointment (`plasticos_facility_profile/models/res_partner_delivery_term.py`). So the supplier's value always counts as set, and the buyer's is never read.
- The PO's `delivery_term` is a stored compute of that same single value (`purchase_inherit.py:12-42`). The load copies it (`load.py:282`), and the Same As Last copy repeats it (`transaction_inherit.py:148`).
- **Bug:** a supplier marked FCFS sends FCFS to the delivery side.

**The sale order defaults to FCFS.** The SO's own `delivery_term` defaults to FCFS (`plasticos_automation/models/sale_order_automation.py:18`). That contradicts the agreed Appointment guardrail, and is a bug.

**A buyer email fires on SO confirmation.** On every SO confirmation with Appointment, `rule_request_dock_appointment` (`plasticos_automation/data/workflow_automations.xml:309-345`) emails the buyer company's main address.
- The timing ignores readiness.
- The recipient is the company, not the receiving site.
- Linda's gate and kill switch do not cover it.

**Linda has no appointment or readiness records.**
- The load holds one planned `pickup_datetime` and one `delivery_datetime`, plus `ready_confirmed_by` and `ready_confirmed_at`.
- Its hours default from a company setting, "M-F: 9:00 AM - 3:00 PM" (`load.py:334-358`), not from the site.
- BRS-03-R016 to R022 are mapped to WP04, with their tests NOT RUN.

**Shipping term is a separate question, and the TODO.md entry about it is wrong.**
- The legacy ERP's shipping term (Delivered / FOB supplier dock) says who arranges freight. That is the native Incoterm (`sale.order.incoterm`, `purchase.order.incoterm_id`). It is not the dock rule.
- Odoo has no native dock rule, so the custom field is justified.
- The `TODO.md` entry that calls `delivery_term` deprecated in favour of Incoterm conflates the two. It is corrected in S0.

## Decision

### 1. Objective (POS-INV-21)

Linda pursues the earliest pickup and delivery, or the earliest export sailing, that both parties accept for a load at or above its minimum net weight.

- She never ships light, and never offers to waive the light-weight deduction.
- She shows the shipper the real calendar early, and lets them choose.
- A ready load triggers a request for an earlier slot or sailing.

### 2. Site dock facts (`res.partner`; ADR-134 §4)

| Field | Status | Rule |
|---|---|---|
| `default_delivery_term`, "Dock Rule" | Existing | **Keeps its Appointment default.** That default is the guardrail that makes Linda verify the rule. It shows on sites, and on companies without sites. Lookup order: site, then commercial company, then Appointment. |
| `dock_rule_confirmed_on` | New, date | Set when Linda or a person gets the site's answer. While it is empty, the Appointment shown is the unverified default, and Linda asks (BRS-03-R016). |
| `shipping_hours` | New, char | Free text in the site's local time, read by people. The load's existing `pickup_hours` and `delivery_hours` default from it, not from the company setting. Empty hours, or an empty native `tz`, make Linda ask the site (BRS-03-R020). |

### 3. Dock rule per side

The existing name `delivery_term` keeps its meaning as the delivery side (rule 91: it has 15+ consumers across 8 modules). Only the pickup side is new.

| Model | Pickup side | Delivery side |
|---|---|---|
| `plasticos.transaction` | `pickup_dock_rule` (**new**). Default: the pickup site's rule, otherwise Appointment. | `delivery_term` (existing). Default: the SO's `partner_shipping_id` site rule, otherwise Appointment. The supplier fallback is removed. |
| `purchase.order` | `pickup_dock_rule` (**new**), a stored compute from its transaction. It replaces the PO's `delivery_term` compute, whose few consumers move to it. | — |
| `sale.order` | — | `delivery_term` (existing). Default: the `partner_shipping_id` site rule, otherwise **Appointment**. This replaces today's FCFS default. |
| `plasticos.load` | `pickup_dock_rule` (**new**). Default: from its transaction. An override needs a reason, as today. | `delivery_term` (existing), unchanged behaviour |

**Which site counts as the pickup site:**
1. the load's `pickup_partner_id`;
2. else the PO vendor's single site;
3. else the PO vendor.

**Migration.** Existing records copy `delivery_term` into `pickup_dock_rule`. Every consumer is listed in the lane brief and updated: the commission dashboard SQL view and its view, the CRM lead field and its views, the automation views and migration, Same As Last, `ci/check_odoo_antipatterns.py`, the tests and `EFFECTIVE_RULES`.

### 4. The SO confirmation email becomes an activity (operator approved 2026-11-17)

- `rule_request_dock_appointment` no longer sends email.
- On SO confirmation with Appointment delivery, it creates one deduplicated `mail.activity`, "Request delivery appointment", for the Logistics group. The activity names the delivery site and the expected ready date.
- `appointment_requested` stays a **stored** field. It is set when the request is actually sent, by a person or later by Linda.
- Existing values are kept. Each `True` is backfilled as one `requested` appointment record.
- At Linda's live cutover, her schedule-window emails (§7) take over these activities.

### 5. Appointments

New model `plasticos.load.appointment`:

| Field | Type |
|---|---|
| `load_id` | many2one, required, `ondelete="cascade"` |
| `side` | selection: pickup, delivery |
| `state` | selection: requested, proposed, accepted, canceled, missed |
| `slot_start`, `slot_end` | datetime (UTC), shown in the site's `tz` |
| `reference` | char: the facility's appointment number |
| `arranged_by` | selection: us, buyer, supplier |
| `proposed_by` | selection: us, counterparty |
| `source_message_id` | many2one to `mail.message`, `ondelete="set null"` |
| `note` | text |

**Rules:**
- **One accepted per side.** At most one accepted appointment per load and side. A new acceptance cancels the previous one and never overwrites it (BRS-03-R018).
- **Changed delivery slot.** Accepting a different delivery slot invalidates the dependent pickup commitment. Its accepted pickup appointment becomes `canceled`, with a reason, and Linda is asked to rebook (BRS-03-R022).
- **Linda's acceptances are gated.** When Linda accepts an appointment, the act goes through the S11 approval gate. A person accepts directly.
- **Replies are proposals until verified.** A reply is a `proposed` record until its sender and its message ancestry are verified, through WP02's `plasticos.logistics.response` binding. Until WP02 binding covers appointment replies, a person records the proposal.
- **No dock-capacity model.** Two loads at one site are not treated as a conflict (BRS-03-R021).

### 6. Readiness (new, on `plasticos.load`)

- `expected_ready_date` (date): the date the shipper reports.
- `ready_net_weight_lbs` (float): the full net weight the shipper says will be staged.

They sit beside `ready_confirmed_by` and `ready_confirmed_at`, so the ready window, the proposal, the confirmation and the planned pickup stay distinct facts (BRS-02-R005).

### 7. Schedule window and flags (evaluated in the existing Linda load-obligation sweep)

The sweep is `plasticos.logistics.request._run_load_obligations`, run by `plasticos.load._cron_check_dispatch_acknowledgments`. It does not run as Linda, and no new `ir.cron` is added. The window is computed at sweep time and stored nowhere.

**Settings** (`ir.config_parameter`, through `res.config.settings`; no new model fields):

| Setting | Default |
|---|---|
| miles per transit day | 500 |
| carrier lead time | 2 business days |
| buffer | 1 day |
| "far" gap | 3 days |
| "near" window | 7 days |

**Computed values** (business days; free-text hours are not parsed):

- **Transit days:** from the accepted carrier quote, otherwise ⌈miles ÷ miles per day⌉. Miles come from the load's `plasticos.freight.estimate.haversine_miles`.
- **Earliest pickup:** the later of `expected_ready_date` and today plus lead time.
- **Earliest delivery:** earliest pickup plus transit days.
- **Staging deadline for a delivery slot X:** X minus transit days, minus the buffer, minus the lead time.
- **Decision date for X:** the last business day on which Linda can still accept X. After it, she falls back to the next slot.

**Linda mode.** `plasticos_logistics.linda_mode` has three values. `off` is the default.

- **off.** The schedule sweep records no activity and no request.
- **shadow.** Each flag opens one deduplicated activity for Logistics and one request in state `shadow`. That request is not sent.
- **live.** Each flag opens the same unsent shadow request, and the activity is assigned to Linda. Sending still waits for the live cutover.

**Flags.** The conditions below run only when the mode is `shadow` or `live`.

| Flag | Condition | Drafted email |
|---|---|---|
| `earlier_option_available` | An available delivery slot X (or export cutoff) falls before earliest delivery, and the next one, Y, is more than "far" days after X | **To the shipper:** "The buyer has an open delivery slot on [X], and the next one is [Y]. To make [X], the full load must be staged by [staging deadline]. Can you have it ready at full weight by then?" Yes: book X. No, or no answer by the decision date: book Y and accept it. |
| `ready_slot_far` | Ready is confirmed, and the accepted slot is more than "far" days after earliest delivery | **To the buyer:** "Material for your PO [#] is ready. We can deliver as early as [earliest delivery]. Is there any chance of a slot sooner than [slot]?" A refusal keeps the accepted slot. |
| `needs_delivery_slot` | Ready, delivery is Appointment, and there is no accepted delivery slot | **To the buyer:** "Ready now. Can we book delivery for [earliest delivery] or later?" |
| `dock_rule_unverified` | A side's site has an empty `dock_rule_confirmed_on` | **To the site:** "Do you require an appointment, or is it first come, first served?" |
| `site_hours_unknown` | The site has empty `shipping_hours` or an empty `tz` | **To the site:** asks for its hours and time zone |

**FCFS pickup.** With an FCFS pickup and the material confirmed ready, no pickup appointment is made. Linda books the delivery slot and dispatches to make it. FCFS proves nothing about readiness (BRS-03-R019).

### 8. Guards (POS-INV-21)

**Light load.**
- `action_schedule` and `action_dispatch` refuse Linda when `ready_net_weight_lbs` is set and is below the transaction's `minimum_net_weight`. That field is the PO's per-shipment minimum, which varies by deal and material (operator decision 2026-11-17).
- A person may override, with a recorded reason.
- No email ever offers to waive the light-weight deduction. Tests assert this over every template.

**Unknown weight.** When `ready_net_weight_lbs` is empty and a minimum exists, Linda asks for the full-weight ready date before proposing any slot.

**Accepted slots.** An accepted slot is never canceled before a replacement is accepted. The exception is the R022 invalidation described in §5.

**Export.** This applies once `plasticos_export` is installed, and is guarded until then.
- When the full-weight ready date misses a booking's cutoff, Linda tells the shipper early. She gives the cutoff, the staging deadline, and the next available cutoff or vessel. A known gap, such as a skipped port call, is stated up front.
- If the shipper cannot make the cutoff, Linda emails **the buyer who provided the booking** and asks to roll it. This is the SOP; the request purpose is `booking_roll_request`, shadow until live.
- Once the buyer's new booking revision is accepted, the existing `booking_amend` request announces it.
- Fees and changes to the earliest return date are human decisions.

**Kill switch.** All new Linda commands go through the S11 gate. Archiving `user_linda` stops them.

## Out of scope

- **Live email sending:** the operator's live-cutover decision, WP10.
- **BRS-05-R036** (rendering currency, time zone and actual fields): unchanged here.
- **Inbound reply parsing beyond WP02's existing binding:** WP02.

## New fields and models (for operator approval)

Each item states why nothing native or existing serves.

| Item | Why it is needed |
|---|---|
| `plasticos.load.appointment` | Odoo has no record of a counterparty dock appointment. `calendar.event` has no load, side, acceptance state or source message, and would put counterparty slots on staff calendars. |
| `pickup_dock_rule` on transaction, PO and load | The pickup side has no field today. The delivery side reuses `delivery_term`. |
| `expected_ready_date` and `ready_net_weight_lbs` on the load | The ready date and full weight a shipper reports have no existing home. `ready_confirmed_at` records confirmation only. |
| `dock_rule_confirmed_on` and `shipping_hours` on `res.partner` | Odoo has no site hours or dock-rule verification. The time zone reuses native `tz`. |
| New request purpose `booking_roll_request` | A selection value, not a field |

**Native or existing pieces reused:** `delivery_term`, `default_delivery_term`, `appointment_requested`, the load's `pickup_hours` and `delivery_hours`, the partner `tz`, `mail.activity`, `minimum_net_weight`, `haversine_miles`, `ir.config_parameter`, and the native Incoterm.
