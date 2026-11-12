# Linda Logistics BRS supersession register

**Effective upon registration:** 2026-10-23. **Source:** explicit operator corrections in the October 23 conversation and the corrected Linda build plan; no claim of implementation or deployment.

These are **narrow amendments**, not edits to the preserved source BRS documents. The operator-directed alignment is implemented in module plan `../LINDA_BUILD_PLAN.md`; the full 60-rule/acceptance crosswalk is there, not in a competing requirements registry. A source heading that says `Candidate` remains untouched by design. All other BRS rules remain requirements.

## Governing interpretations

The physical movement can be one of four legitimate patterns: (1) PO-first pending SO, (2) SO-first pending PO, (3) PO to inventory/warehouse with no current SO, or (4) SO fulfilled from existing inventory without a new PO. Independently eligible purchase and sale orders can be issued and tracked before they match. A missing counterpart is ordinary timing, not a human-approval exception. Native commercial controls stay intact. Never create a fictitious order or company-less load to satisfy the old paired-order assumption.

| Rule ID | Current interpretation |
| --- | --- |
| `BRS-01-R001` | **Creation and issuance are separate**: Linda may resolve/create a native PO or SO only from a specific, complete, source-authorized commercial instruction through its pre-existing Odoo commercial owner, and never invents price, quantity, terms, counterpart or company. Order creation/draft alone cannot send externally. A separate legitimate native live confirmed-state release makes each order independently eligible for supplier/buyer issue, without matching counterpart, fabricated transaction/load or additional Linda-only approval. |
| `BRS-01-R002` | PO-only requests may be identified by company and exact PO without a load or transaction; SO-only requests may be identified by company and exact SO. Physical-movement commands require exact movement/facility identity before acting. |
| `BRS-01-R065` | The Approved-like **external issuance event is per native order**, not an assumed two-sided transaction event. Before creating an order, require a verifiable already-authorized source with complete material, commercial terms, company, counterparty and applicable onboarding/approval checks; otherwise **creation is blocked as an evidence gap**, not performed speculatively. Native live confirmation/approval alone governs issue after creation. |
| `BRS-02-R004` | For an **SO fulfilled from owned inventory**, native stock reservation proves supply but **not physical shipper READY**. The actual warehouse/pickup-site custodian is the shipper for that outbound load and must provide attributable current cargo/material/quantity readiness and available interval at the exact pickup site before physical dispatch. A non-existent supplier PO/confirmation is never created. For real third-party pickup, the real supplier's attributed READY remains required. |
| `BRS-02-R010` | Typed request evidence is order-scoped before a transaction/load exists; require a company and an exact native source order for PO-only or SO-only actions. Load-scoped requests continue to require load identity. **Source-authorized creation evidence** is distinct from a `po_issue`/`so_issue` external-send obligation; only the latter arises after native commercial release. |
| `BRS-02-R011` | PO-only supplier answers may be attributed against PO-scoped requests without fabricating a load/transaction; movement-specific readiness and dispatch still require the proper movement identity. |
| `BRS-02-R013` | Idempotency identity follows the actual action owner and revision: PO, SO, or load as applicable, not a mandatory company/load key for a PO-only request. |
| `BRS-02-R015` | Linda may **resolve/create** complete native commercial orders only through existing Odoo commercial ownership after source authorization is independently proven, and later issue/communicate each order on its **own valid native release**. This is not permission to derive a PO merely from a SO, select price/carrier/supplier, bypass native commercial checks, or mint speculative business facts. The WP00 source-binding gap blocks only creation if unresolved. Ordinary authorized coordination never needs another Linda approval. |
| `BRS-05-R029` | **Canonical load checks protect physical load dispatch, carrier packet release and physical load-state transitions**, including all direct/cron/wizard paths. Independent native PO/SO **commercial order emails** may occur before a load exists and instead require strict **order-scoped** release, company, recipient, revision and mail guards. Stock `assigned` alone never permits dispatch; this does not weaken the real physical-load guard. |
| `BRS-07-R047` | For **PO-only warehouse inbound**, bind authenticated incoming documents to **company + exact PO + request/message**. Classify/verify actual receipt only after linking the **correct incoming `stock.picking`, warehouse and movement** with matching company. If picking is absent, retain the PO-scoped document without falsely marking it received; ambiguous multiple pickings require clarification/review. For **SO-backed outbound**, continue requiring exact load association. No fake load, fuzzy PO/domain match, duplicated original document, or hash-only verification. |
| `BRS-06-R040` | An exception may be scoped to PO/SO while no physical load exists. A load/milestone key is required only when the exception concerns an actual load. |

## Binding source schedules (restatement, not supersession)

The following **existing BRS text is preserved**, not revised. Implement WP03/WP06/WP07/WP08 exactly as mapped in `../LINDA_BUILD_PLAN.md` section 6b and its 60-rule table:

- `BRS-02-R007`: not physically READY -> **one status request Monday morning in supplier-local time**, PO number and shipper, stop on READY/cancel/supersede. Exact hour remains runtime configuration within morning.
- `BRS-06-R039`: separate **supplier confirmation after 24h**, at most one/day, **three unanswered** follow-ups before escalation; separate buyer slot **24h/48h** thresholds; carrier packet ACK **T+2h reminder/T+4h carrier+ops escalation**; still-unacknowledged broker-facing **D-1 09:00 and D 08:00** origin-local; separate **ops-only D-1 13:00 and D 07:00** origin-local; broker-local routine **22:00–06:00 quiet hours**, not a silence requirement for urgent internal exceptions.
- `BRS-07-R051`: Monday–Friday business-day missing-document checks/escalations **supplier +1/+5 after pickup**, **carrier +2/+6 after pickup**, **buyer +1/+5 after delivery**; after due, at most one reminder per party per day, correct missing types/references, single native internal escalation activity to correct owner; stop on cleared/inapplicable/canceled/superseded. No new SMS or `docs@` transport.

These deadlines are business requirements, **not optional example configuration**. Existing Odoo scheduler/job/provider wiring and exact source-local time handling must still be evidenced in WP00; do not claim runtime conformance until cases are executed.

## Additional current operating limits

- Native PO/SO authorization remains required; there is **no blanket per-order Linda approval** and no bypass of native commercial policy.
- `plasticos.transaction.pending_supplier` applies only after actual fulfillment-route prerequisites for that transaction are proven. There is no `all([]) == true` vacuous handoff; for PO-only the supplier follow-up can live on the purchase order itself without a transaction/load.
- PO-only warehouse inventory uses Odoo purchase/receipt (`stock.picking`) evidence; a sale-order-backed `plasticos.load` must not be created without a real SO since `company_id` is derived from it in the inspected baseline.
- An SO can be issued before supply exists, but cannot be physically dispatched until procurement or reserved existing inventory proves supply.
- Supplier/counterparty contacts, freight rate awards, double-blind documents, physical evidence, idempotent outbound mail, and company isolation remain governed by their original relevant BRS rules.
- `BRS-02-R062` remains **deferred** for optional free-form LLM extraction under decision D-05: deterministic reply validation and automatic clarification are the implemented-plan path. Deferral does not erase the candidate clause.
- Unknown native Odoo/transport capabilities remain implementation facts for WP00, not permissions to invent a new approval engine or new transaction type.

## Operator decision 2026-10-24: cancellation notice and post-cancellation release cycle

**Source:** explicit operator decision of October 24, 2026 (contract `LINDA.PR304.CANCEL_REOPEN_LIFECYCLE.2026-10-24`). It amends only the cancellation and re-confirmation behavior of the per-order issue below; same-cycle replay deduplication is unchanged. This is an implementation target with runtime test evidence on PR #304, not a production-readiness claim: live Gmail delivery, the Enterprise runtime and the legacy-to-Linda cutover (WP10) remain unproven.

| Rule ID | Amended interpretation (2026-10-24) |
| --- | --- |
| `BRS-01-R001` | A real, successful native cancellation of a PO or SO whose issue was `sent`, or was `unknown` after an actual transport attempt, queues **one** cancellation notice to that issue's own recorded audience. An issue still queued and never attempted is withdrawn instead, and nothing is sent. Blocked, shadow and proven-undelivered `exception` issues are not retracted. Draft/RFQ cancellations notify nobody. |
| `BRS-01-R065` | Native cancel, then reset to draft, then a new native confirmation (`purchase` / `sale`) is a **new release cycle**: it issues a new revision even when the commercial fingerprint is identical. Reset to draft alone is inert. A repeated approval or confirmation inside an open cycle still issues nothing. |
| `BRS-02-R010` | `po_cancel` / `so_cancel` are order-scoped request purposes on the same exact source order as their issue, linked to the issue they follow up on. They need no counterpart order, transaction or load. |
| `BRS-02-R013` | Issue identity stays company + order + party + purpose + revision. A native cancellation closes the current cycle on its issues. A notice is unique per canceled issue; a repeated cancel of the same episode creates no second notice. |
| `BRS-05-R029` | A cancellation notice goes only to the historical issue recipient (party + address), never to a current-but-unnotified contact, followers, CC or the opposite side. It names only the canceled order, carries no PDF, and uses the logistics2 sender and the native mail queue. |
| `BRS-05-R034` | A notice is `sent` only after native transport reports it. A reissue mail for the same party is held in the queue while an earlier notice to that party is still pending, so a new issue never overtakes its cancellation. |
| `BRS-05-R035` | An in-flight issue (attempted, outcome not recorded) is settled as `unknown` at cancellation, never relabeled `sent`, and counts as communicated. Notice transport failures follow the same `exception` / `unknown` discrimination, with no automatic retry. |

## Operator decision 2026-10-24: D-05 native AI interpretation and the WP02 reply slice

**Source:** explicit operator decision of October 24, 2026 (contract `LINDA.WP02.NATIVE_INBOUND.2026-10-24`) and the operator's 2026-10-25 instruction to publish the slice as **PARTIAL / AI NOT RUN**. D-05's prohibition on every LLM interpretation is superseded **only this far**: free-form candidate extraction may use one native Odoo 19 AI server action with one candidate-recording tool, once that Enterprise capability is verified on the actual runtime. No custom LLM client, provider abstraction, Gate route or substitute inference is authorized. The capability was **not** available to verify, so no AI action is defined yet and free-form replies stay unresolved. This is not a production-readiness claim.

| Rule ID | Amended interpretation (2026-10-24) |
| --- | --- |
| `BRS-02-R009` | Replies arrive only through native Odoo Mail. The native Keep Original copy (`original_email.eml`) on the incoming message is the retained raw evidence and the sole source of its `In-Reply-To` / `References` ancestry. Without it, a reply stays unbound. |
| `BRS-02-R011` | A reply binds to the exact Linda request whose outgoing Message-ID it names, never to the latest request on the order thread. A From address that differs from the request's recorded recipient, or a forwarded message, is unattributed. Because no provider-authenticated sender evidence exists, a matching reply is at most `identity_unverified` and never an accepted commitment. |
| `BRS-02-R012` | Only an explicitly standardized reply (`CONFIRMED` / `CONFIRM` or `NOT READY` as the whole unquoted text) is interpreted, deterministically, as candidate evidence. Any other text is recorded `unresolved` (`ai_not_run`) until the native AI action is verified. Automatic clarification is a later bounded follow-on and sends nothing in this slice. |
| `BRS-02-R014` | A reply to a canceled cycle's issue, or to a cancellation notice, is recorded as stale against that historical request and never rebinds to the current revision. |
| `BRS-02-R062` | Native AI output, once available, is candidate evidence only. Neither it nor any reply changes an order, load, picking, appointment, carrier, mail queue or transaction. |


<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_BEGIN -->
## Operator-requested 2026-10-26 native-first Documents/logistics alignment (proposed until PR admission)

This section is a **narrow additive interpretation** to reconcile the existing 60 source BRS IDs and October 23-25 decisions with the operator's PlasticOS Primary Rev008 and Native-First BRS v1.0.0. It does not delete any historical rule, reverse #304's cancellation cycle, or interpret #305's unrun native AI as implemented. Full exact-ID definitions and status are in `EFFECTIVE_RULES.md` and `EFFECTIVE_RULES.json`; use those with this register for future contracts.

- `BRS-01-R001/R002/R003/R065`, `BRS-02-R010/R013/R015`: PO-only and SO-only native authorization/release are independent. Commercial creation needs genuine previously approved source; physical load, stock receipt and business document are different objects. Never fabricate counterpart order/load or cross-company association.
- `BRS-02-R004/R008`, `BRS-05-R029`, `BRS-06-R042`, `BRS-07-R052/R053`: Odoo Stock reservation does not mean pickup-site READY. Stock operations remain native. Supplier AP, buyer AR and certified scale evidence are not a universal weight field. No automatic financial or inventory transaction from the logistics reminder.
- `BRS-07-R046/R047/R049/R050`: one native Documents original; legitimate multiple **exact typed** PlasticOS evidence links; `plasticos_documents` is sole business classification/verification/override writer; native convenience tags and linked-to field never become second verifier. PO-only warehouse documents may remain with PO pending actual picking/warehouse evidence. No fuzzy or newest-open association.
- `BRS-02-R009`, `BRS-05-R031/R033`, `BRS-07-R046/R051`: native internal Documents Requests and mail.activity are internal; Linda with native Mail owns external supplier/buyer/carrier chase. No external Documents share/portal/Request reminder, duplicate original, cross-party report or leaked dropship buyer shipping address. Supplier-facing report must be QWeb audience-safe or its send fails closed, without banning the legitimate dropship route.
- `BRS-06-R038/R039/R040`, `BRS-07-R051`: readiness Monday, supplier commercial confirmation, buyer appointment, carrier ACK, broker pre-pickup and **three separate document SLAs** retain distinct exact clocks and owners. Document supplier +1/+5 pickup business days, carrier +2/+6 pickup business days, buyer +1/+5 delivery business days. One external Linda reminder per exact company/party/obligation/revision/local day; one current internal Activity; holiday policy remains unknown. Native ir.cron is scheduler substrate, not a new engine or one global job.
- `BRS-07-R045/R048/R054/R056`: buyer Receiving Report is separately verified for the covered quantity and customer invoice; BOL/POD establishes eligible operational events; carrier CST is a separate claim and not a universal invoice/close gate. No `account.move.action_post` from compliance recompute, AI, Linda mail, or file upload. No automatic $150 penalty. QuickBooks remains payment authority until separately authorized migration.
- `BRS-02-R011/R012/R014/R062`: native Gmail/Odoo Mail exact original MIME and ancestor binding remain required. Deterministic standard replies may become candidates only; matching From alone does not authenticate. Native Enterprise AI Manager/guarded Worker is a **conditional future capability**, NOT RUN/NOT ENABLED. It never self-accepts READY, dispatch, stock or money. Free-form responses stay unresolved until actual proof.
- `BRS-05-R030/R034/R035`, `BRS-06-R039`: native queue state is not send evidence. Personal SMTP throttling **before** SMTP is a defer, not an attempt; ambiguous real SMTP outcome is unknown and not auto-retryable. One SO confirmation owner across live/off/shadow, historical-cancellation-before-reissue sequencing, and +2h/+4h ACK relative to actual send are mandatory.
- `BRS-03-*`, `BRS-04-*`, `BRS-06-R037/R041/R043/R044/R068`, `BRS-07-R055`: prior facility, carrier award, appointment and checkpoint rules survive unchanged; no invented rate/approval/scheduler. Internal Activity is the human exception surface.

**Change-control:** This dated section and `EFFECTIVE_RULES*` supersede only the explicit conflicting older *implementation interpretations* named above **after the new BRS PR is operator-admitted**. Other old source rules and the prior October 24/25 supersessions remain in force. Accepted ADRs, commercial/accounting owners and source-specific user rulings are not silently replaced. If an ambiguity remains, stop the affected workflow and obtain a separate decision. No code, cron, email, AI or financial cutover is authorized here.
<!-- LINDA_BRS_NATIVE_ALIGNMENT_20261026_END -->

## 2026-11-05 admission of BRS-POS-10 and seven external-send clauses

This dated admission does not edit the 2026-10-26 overlay above. It admits exactly one copied Native-First chapter, `BRS-POS-10-linda-logistics-commercial-and-physical-communication.md`, recorded in `NATIVE_FIRST_REGISTRY.json`. It admits `BRS-POS-09-R006` through `BRS-POS-09-R012` as Linda external-send obligations. Documents and Activities supply status only. Every other BRS-POS chapter stays a cross-domain reference and is not a second copied authority.

The seven clauses keep their source text in `plasticos_documents`. Their clocks restate, and do not replace, `BRS-02-R007` (supplier Monday status request), `BRS-06-R039` (confirmation, slot, ACK and quiet hours) and `BRS-07-R051` (supplier +1/+5 after pickup, carrier +2/+6 after pickup, buyer +1/+5 after delivery, one reminder per party per day, stop when cleared). No live mail or cron is authorized by this admission.

## Operator decision 2026-11-08: Same As Last copies the last deal

**Source:** explicit operator decision of November 8, 2026. Same As Last creates the next deal from the latest delivered, invoiced, or closed transaction in the company. Buyer, supplier, materials, buy price, sell price, freight carrier, and freight rate stay the same. Only the dates become today. The copies stay drafts. A missing `freight_context_fingerprint` does not exclude that source.

| Rule ID | Amended interpretation (2026-11-08) |
| --- | --- |
| `BRS-04-R023` | The freight resolver still reuses a prior booked rate only when the booking fingerprint matches, and it still refuses to rebuild a missing fingerprint from today's address. `action_same_as_last` is the date-only deal copy. It does not confirm an order, post an invoice, or invent a booking fingerprint. |

## 2026-11-11 Export campaign S2: load company, container journeys, release and actual clocks

**Source:** operator approval of the PlasticOS Export campaign and code grant, 2026-11-11, contract `PLASTICOS-EXPORT-C01-S2-LOGISTICS-FOUNDATION` and its coordinator reconciliation (A1-A13). Architecture: `docs/adr/ADR-130-export-physical-evidence-and-owner-contracts.md`. This section adds interpretations; it does not edit an earlier section or any source BRS file. Export rule IDs (`BRS-EXP-*`) live in the campaign pack until the `plasticos_export` addon registers them.

| Rule ID | Amended interpretation (2026-11-11) |
| --- | --- |
| `BRS-01-R002` | A load's company is its own source company: its sale order's company, or the company named for a buyerless movement. It is never the user's current company. One transaction owns zero or more loads through `plasticos.load.transaction_id`, and each load has at most one parent. A sale order with two eligible transactions is refused, not resolved by picking one (operator decision 2026-11-11). A buyerless load may join only a purchase-backed transaction in its company; no buyer, sale order or transaction is invented. |
| `BRS-01-R065` | Mechanical eligibility of a sale-backed parent still requires the real supplier and buyer. A purchase-backed buyerless parent requires its supplier and purchase orders in the load's company. |
| `BRS-05-R030` | The acknowledgment job escalates once per load per day four hours after the recorded send and no longer resends the dispatch packet. The +2 hour reminder is a Linda-owned notice delivered by the Linda slice; until then no reminder is sent. |
| `BRS-05-R034` | `dispatch_sent` is stamped only when native mail reports the packet sent. A queued or failed send leaves it empty and says so on the load. |
| `BRS-06-R039` | Every route that issues a new instruction (schedule, dispatch, the packet and document composers, direct send, standalone dispatch) passes one Logistics release guard. A hold withholds new release; it never blocks recording a pickup or delivery that already happened. |
| `BRS-07-R051` | Document chase clocks start from `actual_pickup_at` / `actual_delivery_at`, recorded only from evidence attached to the load. A state change, schedule or dispatch time never fills them; a missing actual time leaves the clock unknown. |

## 2026-11-12 Export campaign S9: road equipment, container journey facts, shipment event proposals

**Source:** operator decision 2026-11-12 ("Everything, building features") and contract `PLASTICOS-EXPORT-C10-S9-LOGISTICS-FEATURES`. Architecture: `docs/adr/ADR-130-export-physical-evidence-and-owner-contracts.md`. This section adds interpretations; it does not edit an earlier section or any source BRS file. The J1 journey stays identity only, as the 2026-11-11 section records.

| Rule ID | Amended interpretation (2026-11-12) |
| --- | --- |
| `BRS-EXP-07-R002` | Logistics owns the one domestic road equipment catalog, `plasticos.road.equipment.type`, seeded with 53 ft trailer, 48 ft trailer and flatbed; other types are added as data. A load names its type and states the actual move's dimensions and restrictions. A flatbed has no assumed length, and no payload, VGM or container is inferred from any type. |
| `BRS-EXP-08-R007` | Terminal gate-in, vessel departure, customs filer and delivery partner of a container are Logistics facts on `plasticos.iso.journey.fact`, one immutable row per kind per J1 journey. Only `action_record_gate_in`, `action_record_departure` and `action_record_regulatory_parties` write them, from an original attached to the journey. A later buyer allocation, sale order or resale cannot set, change or delete them. |
| `BRS-EXP-09-R007` | Supplier ready, loaded, gate accepted and sailed are distinct typed proposals on `plasticos.shipment.event.proposal`, each tied to one exact load or journey and its original. Proposing writes nothing else. Accepting runs the owner command with its own prerequisites. A supplier report may support `loaded` for the one load it names; it can never attest a gate-in or a sailing. |
| `BRS-EXP-11-R010` | No proposal or extraction writes `plasticos.load.state`, `plasticos.transaction.state`, a picking or a stock record. One accepted loaded event records that load's actual pickup only; sibling loads, the purchase order's received quantity and its pickings are unchanged. |

## 2026-11-12 Export campaign S9 addendum: container tare, verified gross mass and review closure

**Source:** coordinator C10-SCOPE-2 and C10-SCOPE-4 on contract `PLASTICOS-EXPORT-C10-S9-LOGISTICS-FEATURES`. This section adds to the S9 section above; it edits no source BRS file.

| Rule ID | Amended interpretation (2026-11-12) |
| --- | --- |
| `BRS-EXP-07-R006` | Container tare and VGM weight are Logistics owner facts on `plasticos.iso.journey.fact`, kinds `container_tare` and `verified_gross_mass`, each a weight and a weight unit. Only `action_record_container_tare` and `action_record_verified_gross_mass` write them, from a scale ticket attached to the journey, or, for `verified_gross_mass` only, from an applied Documents `verified_gross_mass` verdict about the same journey in its company. Nothing is inferred from the equipment class or a road equipment type. Export displays them and stores no copy. |
| `BRS-EXP-09-R007` | A proposal that cites a Linda reply takes its asserting party from the answered request's recipient: a purchase-order request is supplier-reported; a booking, acknowledgement or document-chase request is carrier-issued only when its recipient is the carrier of the load. A Linda reply is never terminal-issued. The reply must be current, attributed and about the same load or journey. |
| `BRS-EXP-11-R010` | A Linda reply comes from a supplier or the load's road carrier, so no cited Linda reply supports a `gate_accepted` or `sailed` proposal. The supplier role wins over the carrier role when the same party hauls its own load. Open operator decision (N9): without a cited Linda reply `asserted_by` is the proposer's own label, and the same Logistics user may propose and accept; attachment provenance and separation of duties are not enforced in this slice. |
| `BRS-EXP-08-R007` | Journey facts are readable only by Logistics, Operations Manager and System. A recorded fact has no correction path in this slice; correcting or superseding one (re-weigh, rolled booking, superseded verdict) is an open operator decision. |

## 2026-11-12 Export campaign S11: journey-fact corrections and the Linda sweep cursor

**Source:** operator decisions 2026-11-12 (journey facts may be corrected with a mandatory reason; no second approver for humans; clean up the Linda sweep cursor) and contract `PLASTICOS-EXPORT-C12-S11-FACT-CORRECTIONS-LINDA-APPROVAL`. This section adds to the two S9 sections above and supersedes the S9 addendum's `BRS-EXP-08-R007` sentence "A recorded fact has no correction path in this slice". It edits no source BRS file.

| Rule ID | Amended interpretation (2026-11-12) |
| --- | --- |
| `BRS-EXP-08-R007` | A recorded journey fact may be corrected with `plasticos.iso.journey.fact.action_correct_fact`, which records revision `n + 1` of the same kind with the revision it supersedes, a required reason, its author, its time and its operation key. The superseded row is never written or deleted. Every row is unique on journey, kind and revision; facts recorded before S11 are revision 1. A correction passes the same guards as the first record (the original attached to the journey in its company, visible same-company parties, gate-in before departure, a weight unit and, for a Documents basis, the applied VGM verdict about the same journey); an empty reason, a correction that changes nothing, a stale revision and a reused operation key are refused. The current fact of a kind is its highest revision, read through `plasticos.iso.journey.current_facts()` / `current_fact()`. A human Logistics user needs no second approver. |
| `BRS-EXP-11-R010` | The Linda load-obligation sweep keeps its page cursor in `plasticos.linda.sweep.cursor`, one row per lane and company, and writes no `ir.config_parameter`. Migration 19.0.1.14.24 moved the stored `plasticos_logistics.linda_load_sweep_cursor.<lane>` values once and removed them. The pages, their order and their wrap are unchanged. |

## Change control

Amend this register only for an explicit operator decision or an admitted repository architectural ruling, cite exact BRS IDs, update any associated acceptance tests, and preserve source document bytes. In-scope rule proposals that are unresolved must be marked **proposed**, not disguised as accepted.
