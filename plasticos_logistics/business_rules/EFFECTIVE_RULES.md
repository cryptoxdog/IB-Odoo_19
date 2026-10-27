# Linda logistics effective BRS interpretation, native-first aligned

**Status:** proposed repo-alignment supplement, not deployed Odoo behavior.
**Scope:** seven unchanged source BRS, all 60 stable IDs. Historical source assertions remain unchanged. New effective interpretation here only supersedes explicitly identified contradictions to the latest operator instructions and cross-domain owners.

## Canonical reading order

1. Existing repo and accepted ADR authority; applicable current operator rulings.
2. Historical `BRS-01..07.md` for the original rule and exact ID.
3. `SUPERSESSION.md` for accepted 2026-10-23..25 amendments and this dated 2026-10-26 cross-domain alignment.
4. This effective ID-by-ID register and `NATIVE_DOCUMENTS_INTEROP.md`; BRS-POS references are working cross-domain design, not independently admitted ADRs.
5. `ALIGNMENT_ACCEPTANCE.md` for falsifying cases; installed Odoo 19 Enterprise proof still required.

## BRS-01

### `BRS-01-R001`: Machine release starts Linda with Odoo PO/SO issuance

A PO release and an SO release are independent Odoo-native commercial events. Linda issues only the particular authorized, confirmed order, using native report and Mail; no counterpart PO/SO, PlasticOS transaction or load is required. Commercial source-authorized creation, when explicitly proved, is a separate act and never inferred from the other order. Off/shadow are not live sends. Physical READY remains separate.

*Resolution:* clarified_new_boundary. corrects old all-in-one transaction issuance trigger.

*Cross-domain boundaries:* `BRS-POS-10-R001`, `BRS-POS-10-R002`, `BRS-POS-06-R001`, `BRS-POS-06-R002`, `BRS-POS-06-R003`.

*Validation:* original IDs AC-V01, AC-V02, AC-V18, AC-UI01, AC-UI02, AC-UI03, AC-UI04, AC-BR01 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-01-R002`: Exact transaction/load/PO/SO association

Every obligation binds the actual company and exact source object: a PO-only supplier request binds native PO, an SO-only buyer request binds native SO, a physical dispatch binds the real load, pickup and delivery facts, and a warehouse receipt binds the actual PO/picking. One native Documents original may support multiple exact typed evidence links without duplicate original files. No first-match, partner-recency, orphan or cross-company link.

*Resolution:* clarified_new_boundary. corrects universal transaction/load requirement.

*Cross-domain boundaries:* `BRS-POS-11-R001`, `BRS-POS-03-R002`, `BRS-POS-10-R014`, `BRS-POS-05-R005`.

*Validation:* original IDs AC-V03, AC-V04, AC-V88 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-01-R003`: Company ownership cannot be unknown for automation

Fail closed when company identity or source ownership is unknown or conflicting. Preserve native company and Odoo record rules for original documents, evidence links, commercial orders, stock operations and Linda requests; never use elevated privileges to guess party ownership.

*Resolution:* clarified_new_boundary. strengthens multi-company document isolation.

*Cross-domain boundaries:* `BRS-POS-11-R001`, `BRS-POS-11-R002`, `BRS-POS-03-R014`.

*Validation:* original IDs AC-V04, AC-V80 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-01-R065`: Mechanical transaction eligibility before automatic order issuance

Source authorization for creating commercial orders is distinct from native PO button_approve/purchase and SO action_confirm/sale issuance. Linda must observe actual native commercial policy and approvals; no fake transaction, approval or load and no automatic issuance on draft/import/retry.

*Resolution:* clarified_new_boundary. refines native order release authority.

*Cross-domain boundaries:* `BRS-POS-10-R002`, `BRS-POS-06-R001`, `BRS-POS-01-R008`.

*Validation:* original IDs AC-V02, AC-V84, AC-V90, AC-UI01, AC-UI02, AC-BR01, AC-BR02 plus mapped cross-domain negatives; runtime NOT_RUN.

## BRS-02

### `BRS-02-R004`: Direct shipper READY for every load

For a real outbound load, authenticated source/custodian readiness must evidence exact cargo, available quantity, site and interval. Native reservation (stock.picking assigned) establishes stock availability only, never physical shipper READY or carrier dispatch eligibility. PO-only inbound does not invent a load.

*Resolution:* clarified_new_boundary. preserves READY independent of inventory reservation.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-05-R006`.

*Validation:* original IDs AC-V11, AC-V18, AC-V21, AC-UI05, AC-UI09 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R005`: Ready date versus proposed date

Ready interval, proposal, confirmation time and planned pickup remain different facts.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-01-R009`.

*Validation:* original IDs AC-V17, AC-V55 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R006`: Explicit negative and corrected responses

Not-ready/correction blocks affected commitments, retains previous proof and resumes only through a current accepted revision.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-09-R012`.

*Validation:* original IDs AC-V19, AC-V16, AC-V82 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R007`: Source-defined Monday shipper status cadence

The distinct supplier readiness-status obligation remains one status request Monday morning in supplier-local time for the eligible not-READY PO/load, stopping on READY/cancel/supersession. It is NOT the missing-document SLA of +1/+5 pickup, carrier +2/+6 pickup or buyer +1/+5 delivery. One native cron/scheduler with exact obligation key; no duplicate external notice.

*Resolution:* clarified_new_boundary. separates readiness chase from Documents SLA.

*Cross-domain boundaries:* `BRS-POS-09-R010`, `BRS-POS-09-R011`, `BRS-POS-09-R005`.

*Validation:* original IDs AC-V20, AC-V50 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R008`: Required cargo/equipment facts

Use authoritative physical quantity/weight for the specific commercial/stock movement only. Supplier settlement uses supplier_weight, buyer billing uses buyer_weight; certified CST/scale_weight is evidence/reference only. Do not infer a universal final_weight, use speculative AI extraction, or change supplier/buyer financial terms from a readiness message.

*Resolution:* clarified_new_boundary. prevents logistics overwriting finance weight semantics.

*Cross-domain boundaries:* `BRS-POS-04-R001`, `BRS-POS-04-R002`, `BRS-POS-04-R003`, `BRS-POS-10-R007`.

*Validation:* original IDs AC-V36, AC-V28, AC-V68 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R009`: Google Workspace Gmail through native Odoo Mail

External supplier/buyer/carrier communication uses existing Google Workspace logistics2 sender through native Odoo Mail, with exact Message-ID, original MIME, replies and attachments. Internal native Documents Requests/Activities do not replace Linda external outreach; Documents folder alias is an inbound file channel and does not create an external Documents portal/share.

*Resolution:* clarified_new_boundary. separates native Mail from native Documents Requests.

*Cross-domain boundaries:* `BRS-POS-10-R005`, `BRS-POS-11-R006`, `BRS-POS-02-R003`.

*Validation:* original IDs AC-V09, AC-V10, AC-V78, AC-UI06, AC-UI14 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R010`: Typed request evidence with minimal new persistence

A narrow Linda request/response is durable evidence for exact company + PO/SO/load + party + purpose + revision/touch, linked to native mail transport. Keep original document and evidence link owners in native Documents/plasticos_documents. No duplicate scheduling engine, document file store, state machine or fictional load.

*Resolution:* clarified_new_boundary. clarifies evidence ownership and object scope.

*Cross-domain boundaries:* `BRS-POS-10-R004`, `BRS-POS-10-R005`, `BRS-POS-03-R002`.

*Validation:* original IDs AC-V11, AC-V15, AC-V16, AC-V43, AC-UI06 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R011`: Attributed confirmation through validated reply or secure action

A current reply is only candidate evidence until source/authenticated sender, exact original MIME ancestry, authorized company/party, request and revision have been independently validated. From address alone and an AI result are insufficient for READY, booking, receipt or billing. Retain ambiguous/stale replies for review.

*Resolution:* clarified_new_boundary. strengthens sender and AI evidence boundary.

*Cross-domain boundaries:* `BRS-POS-10-R005`, `BRS-POS-11-R007`, `BRS-POS-03-R005`.

*Validation:* original IDs AC-V11, AC-V12, AC-V13, AC-V14, AC-V84, AC-UI06, AC-UI08, AC-UI09 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R012`: Rules-first interpretation then deterministic fact acceptance

Use deterministic standardized reply parsing first. For free-form ambiguity, only verified installed Odoo 19 Enterprise native AI Server Action (Manager) may propose structured candidates to one guarded native code-tool (Worker). The Worker independently validates original message, exact request, party, revision and business rules; it does not automatically transition stock, loads, commercial orders or financial postings. If AI capability is absent, record ai_not_run/unresolved.

*Resolution:* clarified_new_boundary. formalizes native Odoo AI Manager/Worker without unverified enablement.

*Cross-domain boundaries:* `BRS-POS-10-R006`, `BRS-POS-03-R005`, `BRS-POS-02-R010`.

*Validation:* original IDs AC-V10, AC-V17, AC-V35, AC-V85, AC-UI07, AC-UI08, AC-UI09, AC-UI10 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R013`: Stable business identity independent of payload hash

Identity is company + exact owned PO/SO/load + party + purpose + revision + touch as applicable; payload hash is drift evidence, never an independent right to send. Document reminders additionally bind obligation/document category and event cycle. Concurrency and unknown SMTP outcome do not permit a duplicate message.

*Resolution:* clarified_new_boundary. prevents document-reminder and mail races.

*Cross-domain boundaries:* `BRS-POS-10-R013`, `BRS-POS-09-R010`, `BRS-POS-01-R002`.

*Validation:* original IDs AC-V15, AC-V48, AC-V49 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R014`: Stale, forwarded and contradictory replies

Validate exact request, current revision and party; duplicates are no-ops, conflicts retained, cancelled requests never revived.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R005`, `BRS-POS-09-R012`, `BRS-POS-03-R006`.

*Validation:* original IDs AC-V13, AC-V15, AC-V16, AC-V19, AC-UI10, AC-UI12 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R015`: Linda autonomous routine coordination within distinct commercial boundaries

Linda may coordinate approved existing PO/SO, appointments and carrier communication through native Odoo operations without per-action Linda signoff. It cannot approve carrier awards/rates, create speculative commercial documents, bypass financial review, use AI to assert facts, activate recurring live sends or issue external Documents shares.

*Resolution:* clarified_new_boundary. keeps commercial and financial authority outside Linda.

*Cross-domain boundaries:* `BRS-POS-10-R008`, `BRS-POS-10-R002`, `BRS-POS-06-R001`, `BRS-POS-09-R004`.

*Validation:* original IDs AC-V08, AC-V21, AC-V80, AC-UI05, AC-UI13 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-02-R062`: Bounded LLM may interpret; deterministic rules alone govern action

Conditional future capability only: a tested installed Odoo 19 Enterprise AI Server Action Manager may interpret free-form inbound mail as candidate facts through a guarded native Worker. It is currently NOT RUN; free-form replies remain unresolved until separate proof/approval. No custom LLM client, probabilistic acceptance or direct order/load/picking/posting mutation.

*Resolution:* clarified_new_boundary. supersedes older blanket deferral only as conditional implementation plan.

*Cross-domain boundaries:* `BRS-POS-10-R006`, `BRS-POS-02-R010`, `BRS-POS-09-R016`.

*Validation:* original IDs AC-V10, AC-V67, AC-V78, AC-UI07, AC-UI08, AC-UI10, AC-UI11 plus mapped cross-domain negatives; runtime NOT_RUN.

## BRS-03

### `BRS-03-R016`: Per-facility unknown-safe dock rules

Determine pickup and delivery dock requirements independently; blank/default/unverified differs from confirmed FCFS.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-01-R011`.

*Validation:* original IDs AC-V22, AC-V23, AC-V25 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-03-R017`: Delivery slot constrains pickup scheduling

When destination requires appointment, obtain accepted available slot before final pickup commitment and coordinate feasible pickup around it.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-10-R009`.

*Validation:* original IDs AC-V24, AC-V26, AC-V28 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-03-R018`: Proposal/request/acceptance/cancellation distinction

Keep both-party proposals and explicit accepted slot/reference/source. appointment_requested remains a request indicator only.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R013`, `BRS-POS-09-R012`.

*Validation:* original IDs AC-V26, AC-V29, AC-V81 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-03-R019`: FCFS removes only appointment gate

Confirmed FCFS allows arrival within approved hours but does not prove material ready, immediate loading, truck acceptance or rate authority.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-01-R011`.

*Validation:* original IDs AC-V18, AC-V23, AC-V32 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-03-R020`: Facility time zones, hours and lead time

Persist UTC instants and explicit facility-local windows; unknown hours/time zone require a question to the facility or exception.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-09-R011`, `BRS-POS-10-R010`.

*Validation:* original IDs AC-V27, AC-V28, AC-V52 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-03-R021`: No invented dock-capacity subsystem

Validate exact exclusive slot/resource only where actually known; two loads at a facility need not be an overlap violation.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-01-R001`, `BRS-POS-01-R003`.

*Validation:* original IDs AC-V26, AC-V30 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-03-R022`: Amendment invalidates dependencies

Material accepted slot/readiness changes invalidate only dependent current requests and require renewed commitments; history remains.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R013`, `BRS-POS-09-R012`.

*Validation:* original IDs AC-V16, AC-V29, AC-V38, AC-V82 plus mapped cross-domain negatives; runtime NOT_RUN.

## BRS-04

### `BRS-04-R023`: SAL and canonical executed history

Preserve exact elapsed-time and physical-context matching; reuse prior confirmed/booked rate, not actual invoice variance.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R008`, `BRS-POS-01-R002`.

*Validation:* original IDs AC-V31, AC-V38, AC-V79, AC-UI13 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-04-R024`: Estimate/recommendation/award/actual remain distinct

Nonbinding estimate and ranked recommendation cannot commit rate/carrier; actuals remain executed outcome.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R008`, `BRS-POS-01-R009`.

*Validation:* original IDs AC-V31, AC-V34, AC-V39, AC-V40, AC-V79, AC-UI13 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-04-R025`: Manual-only RFQ after SAL miss

After a genuine current SAL miss, Linda may record and surface the missing commercial rate and coordinate informational follow-up, but no freight rate/carrier award or new outbound carrier RFQ is inferred from autonomous routine logistics authority. The pre-existing freight RFQ episode and any solicitation are manual-only until a separately authorized commercial decision supplies exact current terms. Previously approved/booked valid rate/carrier records can be used for routine follow-through without a redundant Linda human send approval.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R008`, `BRS-POS-01-R011`.

*Validation:* original IDs AC-V33, AC-V34, AC-BR03 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-04-R026`: Immutable market response and recipient evidence

Retain losing, late, declined and superseding quote facts without fabricated send evidence or zero-price declines.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-11-R006`, `BRS-POS-10-R008`.

*Validation:* original IDs AC-V39, AC-V15, AC-V79 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-04-R027`: Carrier commitment beyond approved rate

Linda may autonomously coordinate and dispatch against the exact already-authorized carrier, confirmed freight rate/currency, permitted equipment and validated facility windows. Booking acceptance must be attributable to that carrier and current request; a ranked quote, stale SAL context or estimate is not an award. No additional human prompt is required merely for Linda to execute routine booking or document sends once the commercial authorization exists.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R008`, `BRS-POS-10-R009`.

*Validation:* original IDs AC-V32, AC-V35, AC-V36, AC-BR03 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-04-R028`: Unavailable carrier routes commercial exception

A carrier decline, failed capacity commitment or material freight-context change invalidates affected booking/dispatch commitments. Linda preserves the refusal and old rate evidence, seeks permitted factual clarification autonomously, and raises one commercial re-resolution exception for the existing decision owner. Linda does not select the next-best carrier, change the rate or reroute an unapproved substitute by itself; after the resulting commercial decision, routine coordination resumes automatically.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R008`, `BRS-POS-10-R016`.

*Validation:* original IDs AC-V37, AC-V38, AC-V82, AC-BR03 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-04-R067`: Retain useful working freight; do not repeat predecessor campaign

Current implementation outranks older donor baseline; retain already-satisfied interfaces and regressions.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-01-R003`, `BRS-POS-10-R008`.

*Validation:* original IDs AC-V79, AC-V78, AC-V90 plus mapped cross-domain negatives; runtime NOT_RUN.

## BRS-05

### `BRS-05-R029`: One guarded dispatch authority

One authorized dispatch owner protects every physical load send and transition. Confirm exact company, actual READY, accepted carrier/rate, appointments, packing/document audience and verified relevant quantities first. stock.picking assigned is reservation, not READY or dispatch permission. Independent PO/SO commercial messages require their own release guards, not a load.

*Resolution:* clarified_new_boundary. removes assigned-state carrier side effect.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-10-R009`, `BRS-POS-12-R005`.

*Validation:* original IDs AC-V06, AC-V07, AC-V86 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R030`: Three documents, current version, then acknowledgment

Real load dispatch uses the existing three required, current, audience-safe carrier PDFs/packet, after independent physical eligibility. Carrier acknowledgement timer T+2h reminder/T+4h escalation begins at actual sent transport event, not picking reservation, queue time or order creation. Never re-send the packet as the acknowledgment reminder.

*Resolution:* clarified_new_boundary. preserves dispatch and ACK split.

*Cross-domain boundaries:* `BRS-POS-10-R009`, `BRS-POS-10-R010`, `BRS-POS-11-R004`.

*Validation:* original IDs AC-V41, AC-V42, AC-V53, AC-BR05, AC-BR06 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R031`: Party-specific document and message audiences

Enforce party-specific outbound report and attachment audiences: supplier never receives buyer address/economics or buyer Receiving proof; buyer never receives supplier price; carrier only receives its contractually necessary dispatch data. A dropship PO may need a native QWeb audience-safe variant before supplier issue; do not categorically prohibit the valid native dropship route.

*Resolution:* clarified_new_boundary. adds native dropship report confidentiality.

*Cross-domain boundaries:* `BRS-POS-11-R004`, `BRS-POS-11-R005`, `BRS-POS-10-R003`, `BRS-POS-03-R014`.

*Validation:* original IDs AC-V43, AC-V45, AC-UI03 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R032`: No Sales CC on buyer SO; no archival CC

Apply literal no-Sales-CC on buyer/SO and no buyer/supplier CC on trucker mail; archive in Odoo.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-11-R006`, `BRS-POS-10-R015`.

*Validation:* original IDs AC-V44, AC-V43, AC-UI03 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R033`: No secret leakage through shared notes or chatter

Never leak counterparties or free-text internal notes through native report templates, CC, followers, email context, attachments, chatter or carrier packet. Audience-aware QWeb and sanitized content are required; no blanket copying of linked Documents originals into emails.

*Resolution:* clarified_new_boundary. tightens document and QWeb audience.

*Cross-domain boundaries:* `BRS-POS-11-R004`, `BRS-POS-11-R006`, `BRS-POS-10-R003`.

*Validation:* original IDs AC-V45, AC-V43, AC-V13, AC-UI11 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R034`: Durable queue and truthful send status

Native mail.mail exclusively owns delivery: queued is not sent, native throttle deferral is not an SMTP attempt, sent requires native transport evidence. Linda records one send intent keyed by company/order/party/purpose/revision, guards obsolete PDFs and suppresses duplicate native/legacy confirmations across live/off/shadow.

*Resolution:* clarified_new_boundary. native queue and single mail owner.

*Cross-domain boundaries:* `BRS-POS-10-R004`, `BRS-POS-11-R007`, `BRS-POS-10-R013`.

*Validation:* original IDs AC-V46, AC-V47, AC-V48, AC-UI04, AC-UI14 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R035`: Uncertain SMTP outcome is not safely retryable by default

An actual attempted send with ambiguous remote outcome remains unknown and is never auto-retried; native mail server throttling without SMTP is deferred and remains legitimately retryable. Cancellations notify only historical audiences that actually or potentially received the issue; newer reissues wait for prior notice.

*Resolution:* clarified_new_boundary. distinguishes native throttle from delivery uncertainty.

*Cross-domain boundaries:* `BRS-POS-10-R004`, `BRS-POS-11-R007`, `BRS-POS-10-R013`.

*Validation:* original IDs AC-V47, AC-V49, AC-V77, AC-UI14 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-05-R036`: Currency, time zone and actual fields rendered correctly

Show approved currency and explicit local window, and label planned versus actual checkpoint honestly.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-11-R006`, `BRS-POS-10-R003`.

*Validation:* original IDs AC-V40, AC-V27, AC-V57 plus mapped cross-domain negatives; runtime NOT_RUN.

## BRS-06

### `BRS-06-R037`: One state-dependent milestone clock

One evaluation owner schedules due readiness/slot/ack/checkpoint/doc obligations; other models project it rather than independently chase.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-09-R005`, `BRS-POS-09-R017`, `BRS-POS-10-R010`.

*Validation:* original IDs AC-V20, AC-V53, AC-V59, AC-V75 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R038`: Race-safe due evaluation and catch-up

Due evaluations are idempotent under overlapping Odoo ir.cron runs, per distinct business obligation/party/revision/local date. Do not invent one global scheduler; distinct Linda and Documents internal jobs may coexist, but never duplicate external notice writers.

*Resolution:* clarified_new_boundary. one scheduler platform, distinct concern ownership.

*Cross-domain boundaries:* `BRS-POS-09-R010`, `BRS-POS-09-R012`, `BRS-POS-10-R004`.

*Validation:* original IDs AC-V49, AC-V50, AC-V51, AC-V87 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R039`: Reconcile existing distinct cadence obligations, no invented schedule

Preserve distinct source clocks: supplier readiness Monday supplier-local morning; supplier confirmation 24h, maximum three unanswered touches; buyer slot 24h/48h; carrier dispatch ACK T+2h/+4h from sent dispatch; broker-facing D-1 09:00/D 08:00 source-local; ops-only D-1 13:00/D 07:00; broker-local routine quiet 22:00-06:00. Additionally, separate missing-document reminders: supplier +1/+5 business days after actual pickup, carrier +2/+6 after actual pickup, buyer +1/+5 after actual delivery (Mon-Fri, holiday policy unresolved). No trigger uses transaction create_date.

*Resolution:* clarified_new_boundary. separates all logistics and Documents timing obligations.

*Cross-domain boundaries:* `BRS-POS-09-R007`, `BRS-POS-09-R008`, `BRS-POS-09-R009`, `BRS-POS-10-R010`, `BRS-POS-09-R011`.

*Validation:* original IDs AC-V20, AC-V50, AC-V52, AC-BR04, AC-BR05 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R040`: Actionable, deduplicated human exceptions

Keep one native mail.activity per unresolved exact company/source record/obligation/revision/reason; update and resolve on verified completion, cancellation or supersession. External document chases are Linda Mail actions, never outbound native Documents sharing or auto-generated external Documents Request reminders.

*Resolution:* clarified_new_boundary. one internal activity owner.

*Cross-domain boundaries:* `BRS-POS-09-R003`, `BRS-POS-10-R016`, `BRS-POS-01-R011`.

*Validation:* original IDs AC-V59, AC-V71, AC-V46 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R041`: Checkpoint vocabulary without new load states

Driver assignment, en-route, arrival, pickup, departure, delay and destination arrival are attributed checkpoints; picked_up represents in-transit at load level.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-01-R009`, `BRS-POS-10-R007`.

*Validation:* original IDs AC-V54, AC-V55, AC-V57 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R042`: Pickup proof does not finish delivery picking

Pickup proof and physical source event may advance truthful logistics state, but only actual native stock operation may complete stock.picking; buyer delivery proof does not automatically post a customer invoice. No document-compliance recompute side effect.

*Resolution:* clarified_new_boundary. native stock and Accounting separation.

*Cross-domain boundaries:* `BRS-POS-10-R007`, `BRS-POS-05-R004`, `BRS-POS-06-R011`.

*Validation:* original IDs AC-V54, AC-V69 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R043`: Out-of-order and stale event handling

Retain late evidence, separate physical and receive times; hold missing predecessor; never overwrite delivered with an older delay.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R013`, `BRS-POS-03-R006`, `BRS-POS-09-R012`.

*Validation:* original IDs AC-V55, AC-V56, AC-V58 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R044`: No response after pickup is a monitored exception

Every active load has next expected milestone and due evidence; lost contact/overdue arrival creates an owned exception.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-10-R016`, `BRS-POS-09-R003`.

*Validation:* original IDs AC-V53, AC-V59, AC-V51 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-06-R068`: Minimal operator-facing exception and next action

Show last verified checkpoint, next required fact, owner and blocked reason; routine email threads are not the work queue.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-09-R003`, `BRS-POS-10-R016`.

*Validation:* original IDs AC-V57, AC-V59, AC-V72 plus mapped cross-domain negatives; runtime NOT_RUN.

## BRS-07

### `BRS-07-R045`: Receiver evidence and destination validation

Carrier-reported delivered is only a claim; buyer Receiving Report or attributable receiver evidence is required for verified delivery/invoice eligibility at the exact delivery and quantity. Partial receiving must not certify whole load; BOL/POD and buyer receiving are different evidence classes.

*Resolution:* clarified_new_boundary. separates carrier event, receiving and invoice gate.

*Cross-domain boundaries:* `BRS-POS-03-R009`, `BRS-POS-03-R010`, `BRS-POS-06-R011`.

*Validation:* original IDs AC-V60, AC-V61, AC-V68 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R046`: Store once, preserve original and role views

One original file is held by native documents.document/ir.attachment, with native folder/alias/version history where applicable. Add exact typed links for each legitimately cited transaction, load, PO or picking without duplicating the original; cosmetic native tags/shortcuts do not create new verification truth. Native Documents is internal only; no external links/portal.

*Resolution:* clarified_new_boundary. one original many typed evidence links.

*Cross-domain boundaries:* `BRS-POS-02-R001`, `BRS-POS-03-R003`, `BRS-POS-02-R011`.

*Validation:* original IDs AC-V64, AC-V66, AC-V71 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R047`: Deterministic association before classification

Intake is native Documents folder email alias or manual upload. Exact token/company/PO/SO/load/picking and sender-authorized association only; no partner recency, most-recent-open or fuzzy fallback. PO-only inbound may remain PO scoped until real picking/warehouse identity is proven. Ambiguous/uncertain files stay in Inbox with one internal Activity.

*Resolution:* clarified_new_boundary. exact link and PO-only warehouse evidence.

*Cross-domain boundaries:* `BRS-POS-03-R002`, `BRS-POS-03-R014`, `BRS-POS-05-R005`, `BRS-POS-10-R014`.

*Validation:* original IDs AC-V88, AC-V83, AC-V63 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R048`: Current verified BOL/POD, not checkboxes

Operation-scoped compliance checks actual current verified evidence, not a tag or checkbox. Buyer Receiving Report controls buyer invoice eligibility for the covered quantity; signed/verified BOL/POD controls applicable operational close. Carrier CST/SCALE is separately due but not a universal invoice/close blocker; no automatic $150 penalty for tag absence.

*Resolution:* clarified_new_boundary. document obligation versus operation-specific gate.

*Cross-domain boundaries:* `BRS-POS-03-R007`, `BRS-POS-03-R009`, `BRS-POS-03-R010`, `BRS-POS-03-R011`.

*Validation:* original IDs AC-V62, AC-V63, AC-V65, AC-V67, AC-BR07 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R049`: Native-to-legacy proof synchronization

plasticos_documents is the only authoritative business-classification, verification, exception/override and compliance writer, with native Documents fields as read-only projections/delegations. Multiple exact legacy evidence links may reference one original; no duplicate-original or stale single pointer as source of truth. Synchronization never auto-posts accounting.

*Resolution:* clarified_new_boundary. one verification writer and many links.

*Cross-domain boundaries:* `BRS-POS-03-R001`, `BRS-POS-03-R003`, `BRS-POS-03-R004`, `BRS-POS-03-R006`.

*Validation:* original IDs AC-V64, AC-V63, AC-V66 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R050`: Hash and supersession as integrity, not authority

Document hash identifies bytes/revision and does not establish business authenticity. Supersession invalidates the affected verification; current evidence must be attributable, not stale, expired or canceled. Keep old bytes and history without restoring obsolete acceptance.

*Resolution:* clarified_new_boundary. verified evidence freshness.

*Cross-domain boundaries:* `BRS-POS-02-R007`, `BRS-POS-03-R005`, `BRS-POS-03-R006`.

*Validation:* original IDs AC-V65, AC-V66, AC-V67 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R051`: Party-specific missing-document SLA and escalation

Document reminders are party/obligation/event-specific: supplier +1/+5 business days from actual pickup; carrier +2/+6 from actual pickup; buyer +1/+5 from actual delivery, Monday-Friday until separate holiday ruling. Only Linda sends one external reminder per exact party/obligation/local day. Native Documents Requests and mail.activity are INTERNAL; one active escalation Activity. Stop on verified current evidence, override, cancellation or supersession.

*Resolution:* clarified_new_boundary. the cross-domain Documents SLA/ownership contract.

*Cross-domain boundaries:* `BRS-POS-09-R006`, `BRS-POS-09-R007`, `BRS-POS-09-R008`, `BRS-POS-09-R009`, `BRS-POS-09-R012`.

*Validation:* original IDs AC-V71, AC-V62, AC-BR08, AC-BR09, AC-BR10 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R052`: Quantities, discrepancies and original unit evidence

Retain original quantity/weight source and units for the exact leg. Supplier AP uses supplier_weight, buyer AR uses buyer_weight, certified scale_weight is reference only. Greater-than-5% direct difference prompts human review, with denominator/precision still OPEN. No universal final weight, silent substitution, AI weight extraction or automatic financial adjustment.

*Resolution:* clarified_new_boundary. corrects generic universal selected weight.

*Cross-domain boundaries:* `BRS-POS-04-R001`, `BRS-POS-04-R002`, `BRS-POS-04-R003`, `BRS-POS-04-R004`.

*Validation:* original IDs AC-V68, AC-V61 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R053`: Verified downstream synchronization

Verified physical checkpoints update only appropriate native and PlasticOS operational records via their owner business actions. Stock quants/pickings own inventory custody; only authorized native transitions complete warehouse moves. No inferred stock, load, invoice, credit, penalty or vendor bill from a document event.

*Resolution:* clarified_new_boundary. native stock single writer.

*Cross-domain boundaries:* `BRS-POS-05-R004`, `BRS-POS-06-R009`, `BRS-POS-10-R007`.

*Validation:* original IDs AC-V69, AC-V03, AC-V56 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R054`: Financial close is a separate gate

Operational close consumes verified evidence only; commercial settlement, posted accounting corrections, revenue/margin and payment stay with Accounting and authorized operators. Compliance recompute must be side-effect-free, never account.move.action_post. QuickBooks remains payment owner until a separately approved Odoo cutover; no automatic $150 CST chargeback.

*Resolution:* clarified_new_boundary. finance isolation and QuickBooks exit boundary.

*Cross-domain boundaries:* `BRS-POS-03-R008`, `BRS-POS-06-R009`, `BRS-POS-07-R002`, `BRS-POS-08-R001`.

*Validation:* original IDs AC-V70, AC-V61 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R055`: Truthful operational metrics

Measure event time vs accepted baseline, acknowledgment latency, overdue milestones and human exceptions; no fabricated KPI percentages.

*Resolution:* preserved_original. unchanged business meaning; applicable cross-domain owner boundaries still govern.

*Cross-domain boundaries:* `BRS-POS-07-R011`, `BRS-POS-01-R011`.

*Validation:* original IDs AC-V72, AC-V57 plus mapped cross-domain negatives; runtime NOT_RUN.

### `BRS-07-R056`: Legacy assertions are not confirmed events

Legacy imported and historically unverified evidence cannot start external Linda follow-ups, trigger auto-posting, backfill verified state or invent stock. Enable only proven current eligible cohort after separate activation authorization.

*Resolution:* clarified_new_boundary. historical data is not live evidence.

*Cross-domain boundaries:* `BRS-POS-05-R010`, `BRS-POS-08-R014`, `BRS-POS-09-R014`.

*Validation:* original IDs AC-V73, AC-V62, AC-V05 plus mapped cross-domain negatives; runtime NOT_RUN.

