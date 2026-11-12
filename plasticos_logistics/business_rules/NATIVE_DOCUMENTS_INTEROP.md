# Linda ↔ Documents ↔ Stock ↔ Accounting native-first business contract

**Status:** Operator-requested cross-domain BRS alignment for planned repository adoption. The behavioral constraints below are accepted from PlasticOS Primary Rev008 and Native-First BRS v1.0.0; exact Enterprise module availability, hooks and full installed behavior are still NOT_RUN. This document does not create an Odoo module, model or server action.

## Owned systems and exactly one consequential writer

| Fact/operation | Canonical owner | Linda's permitted action | Forbidden alternative |
| --- | --- | --- | --- |
| Original file, versions, Inbox/alias, native internal Request placeholder | Odoo Enterprise `documents.document` + underlying `ir.attachment` | Refer to exact original; ask internal staff to verify | Second original, separate file store, external Documents portal/share |
| Business evidence classification, typed links, verified status, override, operation-scoped compliance | `plasticos_documents` domain / approved manager action | Read current verified status, request outstanding docs from party | Linda writing verified flag, `documents.document.doc_type` acting as second authority |
| Internal evidence exception/next action | Native `mail.activity` + Documents internal Requests | Open/update one exact internal activity | New ticket/scheduler, repeated Activities per cron tick |
| Supplier/buyer/carrier external document chase | Linda `plasticos_logistics`, native Odoo Mail `mail.mail`/`mail.message` | One external intent per party/obligation/revision/touch | Documents Request reminder plus Linda mail to same external party |
| Commercial PO/SO approval and source report | Native `purchase.order`, `sale.order`, QWeb and Odoo approval | Issue only authorized released commercial artifact | Manufacture counterpart SO/PO, force commercial approval |
| Inventory receipt/reservation/delivery/quantity | Native Odoo Stock `stock.picking`/move/quants | Validate source physical facts; never bypass stock operation | `assigned` reservation treated as dispatch or receipt completion |
| Physical READY/dispatch/ACK and event clock | Existing `plasticos_logistics` load/dispatch guard | Coordinate only attributed real load; maintain exact send evidence | Duplicate carrier sender or four-hour full-packet resend |
| Supplier AP/buyer AR/credit/debit posting | Native Odoo Accounting through accountant-authorized action | Provide verified supporting document/claim | `account.move.action_post()` from document compute, mail, AI or physical state |
| Bank settlement before migration | QuickBooks | No bank writeback, no payment status inference | Activating Odoo dunning or dual-write before authorized QB exit |

## Documents intake and exact association

1. Native Documents folder email aliases and manual uploads receive files. Do not assume Studio AI auto-sort or OCR is installed/free. No external Documents sharing is authorized by this BRS.
2. Preserve one authoritative original. A document citing multiple legitimate loads/transactions can have multiple **typed PlasticOS evidence links**, with independent applicability/verification per business record, pointing to the same original. Native single `Linked to` is not treated as complete multi-record semantic linkage.
3. Bind only exact company + party + PO/SO/load/transaction + source revision; for PO-only warehouse receipt, document can remain PO-scoped until **actual incoming** stock.picking/warehouse is confirmed. No newest-open-transaction guess, fuzzy partner, company-less, latest email thread or duplicate source file.
4. Unmatched or contradictory evidence stays in Inbox with at most one current native Activity. A `CST` tag/scale attachment merely identifies source evidence; it does not prove current certification or authorize money.
5. `plasticos_documents` owns the actual business `verified` / `override` decision. Native fields are projections/delegations, not an independent second writer. Verification is attributable, current, scoped and expiration/supersession aware. A native internal Documents Request is fulfilled only upon verified current business evidence, not merely file upload.
6. A native AI auto-sort may propose cosmetic folder/tag classification only when the installed licensed AI capability is independently proven. It cannot author authoritative compliance, weights, READY, AP/AR or stock.

## Timers are separate business obligations, not one generic cron

| Obligation | Anchor / owner | Clock / condition |
| --- | --- | --- |
| Supplier READY status | Current eligible not-READY supplier PO/load, Linda | Monday **supplier-local morning**, once; stop on READY/cancel/supersede |
| Supplier order confirmation response | Actual sent supplier request, Linda | After 24h; maximum three unanswered followups then escalation |
| Buyer dock-slot reply | Native/verified appointment request, Linda | 24h reminder, 48h escalation |
| Carrier dispatch acknowledgement | **Actual sent** carrier packet, Linda | T+2h reminder, T+4h carrier+ops escalation; never resend packet as reminder |
| Broker pre-pickup schedule | Approved appointment/origin-local calendar, Linda | D-1 09:00 and D 08:00 broker-facing; ops-only D-1 13:00 and D 07:00 |
| Routine quiet hours | Approved broker-local routine messages, Linda | 22:00–06:00; urgent internal exception not suppressed |
| Supplier missing-document evidence | **Actual pickup** timestamp, Documents evaluates / Linda sends | +1 BD external reminder, +5 BD escalation |
| Carrier missing CST/required evidence | **Actual pickup**, Documents evaluates / Linda sends | +2 BD reminder, +6 BD escalation |
| Buyer Receiving document | **Actual delivery**, Documents evaluates / Linda sends | +1 BD reminder, +5 BD escalation |

BD = business days Monday-Friday. Holiday policy remains OPEN. Each doc reminder is exact company/record/party/category/revision/touch and local date with one external mail owner, one internal Activity. A `transaction.create_date` is never a pickup/delivery anchor. Use native `ir.cron` as the only scheduler substrate for due jobs; separate owner jobs may coexist and must be idempotent.

## Weights, receiving, billing and financial effects

- Supplier AP quantity = human-authenticated `supplier_weight` under correct contractual terms. Buyer AR quantity = human-authenticated `buyer_weight` for verified received amount. Certified packaging-adjusted `scale_weight` = reference only. No universal `final_weight`, automatic scale replacement or AI extraction. Direct >5% spread triggers documented human review; precise denominator unresolved.
- Carrier delivery report != verified buyer Receiving Report. Partial receiver proof covers only attributed quantity. Applicable buyer Receiving can gate buyer invoice; CST is an independent carrier compliance/recovery claim and does **not** globally block financial close or automatically cause a $150 penalty.
- Document verification/status recomputation must remain side-effect free. No finance posting, payment, credit/debit, $150 penalty or cash settlement from a Linda email or a document trigger. Operational close and posted accounting close are separate.
- Direct dropship is a legitimate Odoo-native route. Supplier PO must use audience-safe native QWeb variant (or fail closed per send) without buyer shipping name/address; never ban dropship procurement categorically or expose a default unsafe report.

## Logistics handoffs to Documents and Export (2026-11-11, ADR-130)

- **Release guard.** `plasticos.load._physical_release_errors(operation_kind)` is the one Logistics seam for a new physical instruction. `plasticos_documents` adds evidence-policy reasons and `plasticos_export` adds booking or slot holds by ordinary `_inherit`. Logistics imports neither. A reason only withholds release; it never verifies a document, sends mail or changes stock.
- **Actual events.** `plasticos.load.action_record_actual_event` stores the actual pickup or delivery time with a pointer to an original `ir.attachment` already attached to the load. The pointer is a source reference, not a verification: `plasticos_documents` remains the sole business verifier of that original, and Linda remains the sole external sender of any chase it starts.
- **Container journeys.** J1/J2 evidence fields point at the native original (`ondelete="restrict"`). Documents may add J1 as an association subject; it does not copy the original or verify it from J1/J2.
- **No duplicate SMTP or verification.** The acknowledgment job escalates internally and no longer resends the packet; Logistics stamps `dispatch_sent` only on a confirmed native send.

## Native AI inference, explicitly NOT active

Odoo 19 Enterprise AI Server Action Manager may choose a native guarded Execute Code Worker with explicitly declared arguments, once exact installed capability and licensing are verified. The Worker must independently reject untrusted reply text, stale ancestry, unauthenticated sender, wrong company/party, canceled cycle, unresolved conflicts and any request to accept READY, approve rate, send, change orders/stock or post accounting. Candidate output remains append-only evidence pending authenticated validation. No custom LLM client, no external orchestration, and no invented native AI XML field names. If unavailable, persist `ai_not_run` and one internal exception.

## Publication and activation separation

Installing these **BRS files only** must never install or activate a `base.automation`, scheduled job, mail template, Odoo AI action, report or change a mail provider. No live dispatch, payment, document request, Gmail delivery or QB cutover follows from policy installation. Subsequent code contracts reference exact BRS IDs and actual installed Odoo Enterprise evidence.

### Official capability reference, not runtime proof

- Odoo 19 Documents: https://www.odoo.com/documentation/19.0/applications/productivity/documents.html (internal Requests, alias, versions, linked record, optional AI auto-sort).
- Odoo 19 AI Server Actions: https://www.odoo.com/documentation/19.0/applications/productivity/ai/server-actions.html (Manager selects Worker; Worker enforces business rules).
- Odoo 19 automation rules: https://www.odoo.com/documentation/19.0/applications/studio/automated_actions.html (timing/event triggers; Studio/custom-code pricing must be checked).
