# PlasticOS Export | Cross-module integration contracts, v2.6 candidate

**Contract family:** `EXP-IC-01` through `EXP-IC-07` (local proposal identifiers, NOT new BRS IDs or L9 law).  
**Disposition:** CANDIDATE FOR EXISTING OWNER ADOPTION. Logical input/output shapes below are required *semantic properties*, NOT declarations of existing Odoo models, methods, endpoints, events, schemas, installed providers, or executable code.  
**Frozen business target:** Operator-frozen Export Phase 1, 2026-10-28. This document refines its existing handoffs; it does not revise that business architecture.  
**Observed target source:** `cryptoxdog/IB-Odoo_19`, `Staging@04bd0594a7c9dcad53d9c45fc65276d76817c112`, rechecked 2026-10-28.  
**L9 source inspected:** `Quantum-L9/.github`, `main@3dcdeaae355b6de08562993f705084d7a3714bfd`. A current producer-validated GAR observer projection/AuthorityResolution, independently validated EvidenceAssessment and GARReceipt are NOT AVAILABLE for this pack.  
**Governing repository law:** current `INVARIANTS.md` v2.2.0. `GOVERNANCE/ODOO_INVARIANTS_v3.3.0_DRAFT_r1.md` is a working **DRAFT**, including POS-INV-01..25 and BAN001; no draft text overrides the repository constitution.  
**Implementation, migrations, Enterprise tests, owner approvals, external correspondence, deployment:** NOT_RUN / NOT_AUTHORIZED.  
**Private evidence:** `EXPORT_BRS/SOURCES/` is INTERNAL ONLY. Neither these files nor the entire ZIP may be committed to a public repository.

## 0. Reading path and contract authority

1. Read `EXPORT_BRS/CONVERGENCE/OPERATOR_DESIGN_FREEZE.md`, then `EXPORT_BRS/MODULE_DESIGN/IMPLEMENTATION_READINESS_CONTRACT.md`, then **this file** before authoring cross-addon interfaces.
2. The 120 unchanged `EXPORT_BRS/REGISTRY/rules.json` and `EXPORT_BRS/RULES/BRS-EXP-*.md` records own Export business rules. The 120 unchanged `ACCEPTANCE/cases.json` cases own their source-positive and source-negative tests. `RULE_REALIZATION_MATRIX.csv` maps rules to existing owner gaps. `EXP-IC-*` identifies **interfaces needed to realize** those rules; it does not create 7 new business-rule owners.
3. `EXPORT_BRS/INTEROP/TARGET_OWNER_BRS_AMENDMENTS.md`, `CONVERGENCE/TARGET_OWNER_HANDOFF.md`, and this file are *proposed* cross-owner changes. Each existing owner must accept its own effective BRS/ADR and technical realization at an exact target revision. The Export pack cannot itself change Logistics, Transaction, Documents, Linda, Stock, Sale, Purchase, Accounting or Enterprise platform law.
4. Historical addenda, `DECISION_FRONTIER.md` and predecessor iterations preserve provenance; they do not silently reopen or outrank the 2026-10-28 operator freeze. No candidate technical field name here is a locked physical database field or permission to create an addon.

## 1. Common boundary vocabulary and cardinalities

**One owner per kind of truth:**

| Kind of fact / effect | Authority | Export's legal involvement |
| --- | --- | --- |
| Native PO/SO terms, party, order lines and approval | Native Purchase/Sales | Authoritative read and typed source-line reference; never invent order or price |
| Custody, stock quantity, actual receipt/delivery, pickings, packages, physical weight provenance | Native Stock and correct physical owner | Authorized read and discrepancy display; never write stock or billable weight |
| Transaction-to-executed-shipment binding | `plasticos_transaction` + `plasticos_logistics` at their agreed seam | Exact reference to accepted binding; never match first by SO |
| Load identity, company/movement validity, actual ISO container/seal journey, carrier, rate, scheduling, dispatch, terminal milestones when accepted | Logistics/Stock as selected by source-owner decision | Read and supply approved export constraints; do not create false load, gate-in or dispatch |
| Carrier reservation, accepted booking revisions, booking equipment slots, planned slot-to-cargo association | `plasticos_export` if existing reuse proof remains negative | Authoritative only for these narrow export facts; cannot promote planned slots into actual movement |
| Native original file, versions, intake | Enterprise `documents.document`/`ir.attachment` | Read/link exact original, without copying binary |
| Typed evidence associations, current verification/overrides, operation-specific document obligation outcome | `plasticos_documents`; native bridge delegates | Read scoped verdict, propose candidate link; never verify or override independently |
| Outbound purpose, recipient, attempt, queue, sent/unknown delivery | `plasticos_logistics` Linda through native Odoo Mail | Request separately authorized intent; never be external sender |
| Native AP/AR/credit/payment/settlement | Accounting and current authorized settlement writer | Read approved outcomes only; no post/reconcile |
| Dashboard and printable Export-specific layout | Export projection over all above | Access-controlled views and QWeb; no report-owned source of truth |

**Distinct identity/grain obligations:** One SO or PO can feed multiple actual movements; one booking can reserve several equipment slots; one slot can serve several **cargo-source lines** while counting once; one actual ISO container/journey must not be inferred from a booking slot or a stock package. A real PO-only receipt can exist without a transaction/load or buyer. Where an actual transaction/load one-to-one relation is valid, keep its identity. Do not impose a universal one-slot/one-PO, one-slot/one-order-line, one-booking/one-load, one-booking/one-SO, or one-physical-container/one-inland-leg relation. Later sale allocation never rewrites physical history.

**Cross-owner data obligations (required attributes, not a new platform envelope):** Each consequential handoff identifies the real `company_id`, source-owned subject kind and exact record identity, purpose/action, effective source revision, attributable evidence/provenance, authorized actor/role, intended audience when external, applicability and time precision, and an idempotent logical-operation identity when a mutation is requested. A missing/ambiguous required attribute is not inferred from partner, order name, latest record, AI score, current company context, or booking-number resemblance. Do NOT persist a new universal integration envelope or build a message bus for this proposal.

**Outcome distinctions:** `eligible`, `pending/review`, `not_applicable`, `stale`, `ambiguous`, `blocked`, and `not_available` denote different business outcomes. A calculated projection cannot be interpreted as an acceptance, a returned record as a sent email, a booking as gate-in, or a NULL as zero. These are design semantics, not a proposed global Odoo enum or L9 result algebra. Fail closed only the affected consequential operation; unrelated legitimate domestic/PO-only work must continue.

## 2. EXP-IC-01 | Commercial order and native fulfillment source contract

**Producer / owner:** native `purchase.order`/lines, `sale.order`/lines, actual Odoo Stock move, picking and custody owner. `plasticos.transaction` owns its existing commercial execution references.  
**Consumer:** Export slot/manifest/report. **Dependent gates:** `EXP-GAP-01`, `EXP-GAP-05`, `EXP-GAP-06`.  
**Source business rules:** BRS-EXP-01-R001..R004; 02-R001; 06-R003; 08-R001..R004, R006..R007; 11-R007,R010; 14-R006,R008.

**Source read contract:** for every proposed cargo participation return/check exact company, real source PO/SO **line** where applicable, product/UoM, agreed quantity and actual reservation/receipt/delivery evidence separately, actual picking/move identities when they exist, ownership/custody, source status and timestamp. An order-header ID alone cannot prove per-load fulfillment; `plasticos.transaction` may group commercial context but cannot substitute its computed `final_weight` for accepted AP, AR, carrier-certified net or VGM. For actual non-owned 3PL/dropship movement where no stock move is applicable, record an attributable alternative source and mark physical measurement/receipt independently pending until verified.

**Consumer command boundary:** Export MAY plan booking space against an *eligible* source reference and create its own prospective cargo-to-slot link. It SHALL NOT reserve stock, deliver, issue orders, change buyer, change PO/SO quantities, alter price, create a native movement, or declare source line fulfilled. Native owner commands alone mutate their respective facts. A late real sale adds a new native Sales allocation without rewriting prior purchase/custody/terminal events.

**Reject or hold:** wrong company, invalid line, unapproved sale, insufficient/unverified source quantity, conflicting UoM conversion, duplicate commitment against the same real source, and an attempt to count a planned slot as shipped. Existing native stock availability/contractual allocation rules are authoritative; the precise installed stock/move interface and any legal non-stock pathway require owner proof.

**Idempotency and proof:** repeat planned link with the same source identity/revision must not double-allocate; cancellation does not reverse actual native fulfillment. Enterprise witness: 30-load SO + four-load PO, four partial movements, correct remaining balances, no source header duplication, and two attempts to allocate the same real fulfilled quantity to different sales.

## 3. EXP-IC-02 | Exact transaction, load and ISO-container journey binding

**Producer / owner:** `plasticos_logistics` with `plasticos_transaction`, and native Stock where physical packaging/moves are applicable.  
**Consumer:** Export booking slots, manifests and Logistics-facing links. **Dependent gates:** `EXP-GAP-01`, `EXP-GAP-02`.  
**Source business rules:** BRS-EXP-02-R001; 07-R001,R004..R008; 08-R005,R006,R008; 10-R007; 13-R005; 14-R002,R015.

**Authoritative owner correction required before implementation:** `plasticos_logistics/models/load.py` currently derives `company_id` solely from `sale_order_id.company_id` and its `create` path picks the first matching transaction for an SO. `plasticos_logistics/models/transaction_inherit.py` has a one-load-per-transaction constraint plus a universal supplier-and-buyer requirement. This is **not** sufficient for buyer-unassigned, same-SO/many-shipments or ambiguous multiple real shipments. Logistics/Transaction must preserve existing valid 1:1 execution links but bind them by exact physical shipment authority, establish stable company from authorized movement source (not sale order alone), and use route-specific eligibility. A PO-only receipt remains possible without inventing a transaction or load. Reconcile old links in owner migration; ambiguous links are review population, not automatic replacement.

**Binding input (semantic minimum):** actual company; explicitly selected existing load and existing shipment/transaction if eligible; actual movement source and identity; supplier or authorized custodian; pickup and physical destination; applicable native PO/SO/stock identities and company coherence; evidence authorizing the association; requested applicable booking slot/revision; actor. At planning time `load_id`, physical ISO number and seal MAY be unknown. The plan must not invent them.

**Physical-unit input/output when actually known:** a single source-owned physical ISO equipment identity, source-attributed ISO number, equipment class, seal as evidenced at the relevant journey/event, binding to the actual outbound journey and supporting native stock/package IDs *without conflating any two identities*. A reused ISO number on a later voyage is not a new unique global container; a packaging line marked "Container" is not proven to be a shipping ISO unit. Resolve the physical owner and field/model representation by an exact installed source/capability census; if no native/existing source can carry it, only that owner may admit a minimal extension. Do not assume `load.trailer_number`, `load.seal_number` or `transaction.line.container_no` already satisfy the obligation.

**Output semantics:** exact accepted link or explicit `unresolved/ambiguous` with the conflicting candidates; independently observed physical milestones; no movement state promotion. One outbound unit may have multiple contributing PO/stock lines and potentially more than one real feeder movement; avoid enforcing a universal slot-to-inland-load 1:1. Any executed shipment/load link that is unique in the selected owner remains single-valued for that specific execution. The v2.5 candidate `booking.slot.load_id` is not sufficient proof that a single optional FK covers a multi-feeder shipment; the actual physical-owner association and its cardinality must be witnessed before freezing that field.

**Reject or hold:** first-by-SO guess, wrong-company or implied buyer, treating reservation/`assigned` as dispatch, two current conflicting physical identities in one occupied slot, invalid duplicate use of one physical execution, unproved terminal gate-in, and rewrite of already accepted past physical events after a booking amendment.

**Proof:** real 30/4/4 shared-order case; buyerless PO/owned cargo and supplier-FAS case; five distinct ISO journeys from four POs under one booking; same ISO reused on different journeys, distinct seals; multiple cargo-source lines per slot; a direct and wizard/cron dispatch attempt that cannot bypass owner guards. Preserve domestic regression behavior.

## 4. EXP-IC-03 | Booking capacity and source-line allocation contract

**Authoritative writer:** Export only for carrier-confirmed booking slot commitment; native Purchase/Sale/Stock and Logistics own source quantities and physical execution.  
**Consumers:** Export booking control center, native source views and reporting; Logistics may read only the approved slot assignment as *a constraint*, not a physical delivery. **Dependent gates:** `EXP-GAP-02`, `EXP-GAP-05`.  
**Source business rules:** BRS-EXP-07-R003,R004,R007,R008; 08-R005,R006; 13-R005; 14-R014..R016,R018..R019.

**Allocation command input:** booking id and effective accepted revision id/digest, company, **single exact slot or unique available capacity unit**, equipment class, one or more qualified real source-line references with planned quantity and native UoM, optional exactly evidenced load/physical journey, authorization and stable operation identity. The source order line may contribute to more than one shipment through valid partial quantities, but not exceed native eligibility. The booking may be created before a PO/load exists; this does not make tentative/unconfirmed capacity available or create fictitious cargo.

**Preconditions:** source-confirmed equipment class and count at the current accepted revision; slot has at most one active reservation for that capacity unit; source ownership/quantity eligible; referenced company consistent and actor authorized. Under concurrent attempts, serialize the shared capacity claim and recheck **inside the same database transaction**. `@api.constrains` or a read followed by write without locking is not sufficient.

**Result:** committed/released/replaced slot participation **with immutable prior history**, exact selected company/booking/current revision, distinct equipment slot count and independently sourced fulfillment amounts. Each slot may have several cargo lines but still counts as one slot; a confirmed five-slot booking with five assigned slots has zero remaining, even with four supplier POs. The actual ISO number is joined later from EXP-IC-02, never generated by allocating space.

**Revision and failure:** when source-confirmed count drops from five to four with five valid past commitments, preserve five occupied historical units, show over-allocation=1 and block unsafe **new** assignment. Do not remove loaded units or silently add available capacity after physical shipment. Explicitly reject stale revision, incompatible class/substitution, duplicate active claim, allocation beyond native source-line quantity, incompatible company or a replay with conflicting payload. Idempotent exact replay returns existing outcome without duplicating links.

**Proof:** two concurrent attempts for last capacity unit yield one accepted and one rejected/review outcome; an unchanged replay creates no second link; a multi-line mixed-grade slot counts once; a rolled booking cannot revive expired capacity or erase a real loaded container. All native stock/valuation remain unchanged by these commands.

## 5. EXP-IC-04 | Documents originals, typed links, verification and AI candidates

**Owner:** native Enterprise Documents/attachments for original bytes and versions; `plasticos_documents` for exact typed evidence link, verification/override, applicability evaluation and expiration; optional native AI only as input producer. `plasticos_documents_native` delegates; **Export never writes the verification decision**.  
**Consumers:** Export booking revision acceptance and readiness, Logistics release, Linda attachments/obligations. **Dependent gate:** `EXP-GAP-03`, plus installed Enterprise proof `EXP-GAP-06`.  
**Source business rules:** BRS-EXP-03-R001..R003,R006,R007; 09-R001..R008; 11-R001..R006,R008,R009; 14-R020.

**Candidate association input:** source original ID (native Documents, or separately approved underlying original), native file/version identity, company and attributed sender/party role, typed target `booking`/`booking_revision`/`slot`/`load`/`transaction`/`native PO or picking` as applicable, purpose/doc class and relevant quantities or shipment coverage, source message/date, candidate extraction and exact evidence pointers. An email, PDF, photo link and spreadsheet may be distinct original/source objects. One original MAY have several typed links; each link has independent scope, currentness and applicability. A link based only on newest partner, filename, hash equality, model default or AI confidence is candidate-only and not authoritative.

**Authoritative result (observational evaluation):** for one exact `company + subject + operation/purpose + document class + applicable revision`, return source-original reference, typed association, current source/version, effective verified/authorized-override verdict, verifier/override provenance, expiry/supersession, reason and missing/ambiguous state. Do **not** call existing `plasticos.compliance.service.get_missing_documents(..., purpose="export")` as an established API: inspected source currently only maps invoice/close purposes. The new operation-scoped owner behavior needs a separately accepted Documents owner contract and Enterprise fixture. Evaluation has no side effects, posting, sends or approval changes.

**Accept/apply separation:** native AI/document extraction may prepare proposed booking fields with original-byte/source-field citations, but Documents association and verification require their designated authority. Export may independently accept a **booking term revision** only through its authorized acceptance command after exact identity/evidence gating; this is NOT document verification or approval of a physical event. The source business rule determines which booking fields may be accepted through what review policy. No AI process may set buyer/supplier commercial weights, verified flag, inventory, freight award or load state.

**Reject or hold:** a same-partner four-week document guessed to newest transaction; one file version inheriting verification of different bytes; revoked/expired evidence; ambiguous company/carrier/booking/slot association; one original silently copied into multiple binary stores; AI-detected `gate in` counted as official accepted gate-in; unauthorized reader of a restricted source. Current `documents.document.action_verify` and `plasticos.document.action_verify` cannot remain two independent sources of one business verification truth.

**Owner acceptance / proof:** choose the smallest legal association representation after inspecting actual installed native linkage. Reuse one original; show it supporting two correctly distinct scoped obligations, with separate verdicts, and a later superseding source changing only the affected obligation. Verify Enterprise record rules and actual native version, attachment, Request and AI availability; if a required API is absent mark `NOT_AVAILABLE`, do not imitate it in Export.

## 6. EXP-IC-05 | Export revision to Logistics movement/feasibility contract

**Producer:** `plasticos_export` accepted booking snapshot/field-level delta, sourced from authoritative booking originals.  
**Decision owner / consumer:** `plasticos_logistics`, with native Stock/picking and customer/supplier commercial owners as needed. **Dependent gates:** `EXP-GAP-01`, `EXP-GAP-02`, `EXP-GAP-04`, `EXP-GAP-05`.  
**Source business rules:** BRS-EXP-02-R002..R005; 04-R001..R004; 07-R001..R007; 10-R001,R004..R008; 11-R005,R006,R011; 13-R002..R004.

**Read-only current context (minimum):** booking identity and company; current accepted revision and source original/provenance; confirmed equipment classes/count; exact associated slot/movement if any; carrier/forwarder; actual supplier/custodian; origin and terminal/ramp destination distinct from buyer; source-local ERD, cargo gate cutoff, document cutoff and VGM cutoff with each independent timezone, precision and UTC normalization **only when evidenced**; changed field keys with affected slot/load ids as scope candidates; revision-effective timestamp and conflicting/unresolved indicators. Commercial contract risk point/Incoterm remains sourced to real native contract, not inferred from industry `FOB pickup` or `FAS port` shorthand.

**Source-to-owner handoff:** Export may expose a current snapshot and an identified material revision delta, but **does not issue a dispatch command**. Logistics must re-read the current revision immediately before its own booking/rate/schedule/dispatch or packet release, validate company, equipment/chassis, terminal hours, current local-time feasibility and all existing dispatch gates, and decide the effect. A stale/ambiguous context holds only the impacted consequential export action. A booked/assigned slot by itself does not authorize a carrier, physical dispatch, terminal acceptance, vessel loading, insurance/risk handoff or Stock write.

**Revision behavior:** for a week-three cutoff roll, Logistics re-evaluates week-three pending rate, appointment, work-order and carrier intent. It MUST NOT automatically cancel four sibling movements, change a confirmed freight rate, reissue a PO, resend an uncertain mail, or erase week-one accepted events. Already sent/unknown communications remain Linda-owned immutable evidence. If new source affects a completed historic act, retain that act and create a current exception/correction route, not retrospective state mutation.

**Dependency direction / enforceability:** `plasticos_export` is downstream of Logistics and Documents. `plasticos_logistics` MUST NOT import/export-depend on `plasticos_export`. The admissible implementation pattern is a **source-owner-approved narrow Odoo extension at the existing load command/transition boundary** from the installed downstream Export addon, or an equivalently verified owner-controlled interface that retains an acyclic manifest. The owner must show all physical release paths (button, ORM, wizard, cron, direct transition) evaluate the same relevant constraints; merely adding an Export UI warning or unchecked callback is insufficient. Current method availability and extension semantics are to be proved at the exact installed runtime; no proposed hook name here is executable.

**Physical counterexamples:** supplier FAS-delivered cargo may have no company-hired drayage or Linda carrier packet; a reservation cannot prove supplier READY; actual gate arrival cannot prove terminal gate acceptance; unknown timezone/DST ambiguity cannot silently turn into an exact cutoff; a domestic non-export load must not suddenly require a booking.

**Proof:** accept source roll but no dispatch/automated send; revalidate only actual related pending obligations; rerun freight-context/current-equipment checks and domestic paths; support verified manual evidence without barcode/device mandate.

## 7. EXP-IC-06 | Linda-only booking correspondence and carrier packets

**Producer:** authorized Export booking issuer/revision context; approved native commercial order and Logistics movement context as separate input sources.  
**Owner/consumer:** `plasticos_logistics` Linda outbound intent, native `mail.mail`/`mail.message` for queue/send, approved Logistics QWeb for a real drayage Work Order. **Dependent gate:** `EXP-GAP-04` (+ `EXP-GAP-03` for required verified documents).  
**Source business rules:** BRS-EXP-03-R004..R006; 10-R002..R004,R008; 11-R011; 06-R001; 14-R010.

**Logical booking-send request, not an existing method:** company, real booking and accepted effective revision, source original/reference, `booking_issue | booking_amendment | booking_cancel` purpose, authorized operator/release decision, company-specific party/recipient and disclosure audience, exact intended attachment revisions, optional exact affected physical load for company-managed drayage, independent business cycle/operation identity, and current payload fingerprint. An approved supplier PO issue is **a different purpose and an independent native order release**: a later weekly booking must not repeat the unchanged PO issuance merely to send a booking. A standalone booking PDF and a drayage Work Order are separately recognizable artifacts when a carrier packet is actually applicable.

**Owner validation before effect:** Linda rechecks business authorization, current revision/recipient/company and party identity, evidence requirements and non-confidential content at the send boundary; records per-party/per-purpose/per-revision obligation identity, one outbound intent, accepted queue state, native provider send/unknown state and acknowledgment separately. A booking document must never expose another party's purchase/sales price or an unrelated customer identity to a drayage carrier. `off`, `shadow` and `live` remain distinct; installation/import/test/replay cannot send. A supplier FAS delivery with no company-arranged truck generates **no** drayage packet by default.

**Existing-owner implementation blocker:** current `plasticos.logistics.request` explicitly allows only PO/SO issue/cancel and its SQL CHECK requires exactly one PO or SO. An Export-side `selection_add`, fake PO, fabricated SO, or direct `mail.mail` send does not solve this contract. The Logistics/Linda owner must adopt a **narrow booking-source obligation** within its existing mail/evidence authority: either extend the current owner-owned request model with a safe source-kind/source-revision identity and correct constraints/upgrade, or prove a smaller existing native Linda extension can satisfy the same lifecycle. Avoid a second queue, generic messaging framework or upstream dependency on Export. If a safe realization remains impossible without a new owner model, the owner must justify it with an irreducibility counterexample and approval, not silently add it.

**Result semantics:** blocked/shadow/queued/sent/failed/unknown/cancelled are NOT synonymous. Native queue acceptance is not provider delivery, and provider acceptance is not carrier acknowledgment. An uncertain send MUST NOT be retried automatically; reconcile first. A material revision invalidates/reissues only the affected **unsent** intent as permitted. Sent evidence remains; valid cancellation and reconfirmation create distinct ordered obligations per source owner's approved lifecycle.

**Proof:** one PO legitimately issued before any booking, four later booking notices and one unchanged PO; independent intended parties; cancellation/roll after queued and after sent; provider timeout -> unknown and no duplicate send; domestic approved packet unchanged; company-managed drayage packet includes current Booking and Work Order but never supplier price/margin/buyer confidential data.

## 8. EXP-IC-07 | Reports, dashboards, security and currentness

**Producers:** Export accepted booking/slots, native Sale/Purchase/Stock, exact Logistics physical status, Documents current verification, Linda send evidence, Accounting actual postings if included.  
**Consumer/owner of presentation:** native Odoo report/list/search/pivot/spreadsheet and Export-specific read-only QWeb layout. **Dependent gates:** `EXP-GAP-05`, `EXP-GAP-06`, affected owner gaps.  
**Source business rules:** BRS-EXP-06-R001..R003; 13-R009,R010; 14-R001..R012,R017..R022.

**Six frozen report populations:** Booking Space Availability (booking+equipment class, current revision); Booking Allocation/Container Manifest (slot or actual ISO journey, distinguished); Open PO/SO Fulfillment (native order line and actual Stock/owner execution); Container Shipment Register (one source-owned physical container+journey); Cutoff & Booking Exceptions (exact affected booking slot/load+revision); Missing Export Documents (exact operation+subject+document requirement). A dashboard is an actionable summary over these populations, never their replacement.

**Projection input:** exact owner record IDs, company/current user rights, permitted party audience, period, granular source/revision/as-of semantics, source precision, unknown/missing/provisional/confirmed states. Every report states its grain and the distinct-count/quantity aggregation strategy. Avoid many-to-many cartesian counting: one slot with 2 PO lines counts as one slot; an original document linked to 3 loads is one original but 3 applicable links; 5 containers from 4 POs are five container journeys, not twenty. Booking capacity, accepted supplier weight, buyer billing weight, tare and certified VGM are different columns and authority sources.

**Presentation and action:** every dashboard metric links with the same company, authorized record population, user filter, reporting period, source revision/time and implied grain to the exact native list/form/evidence. Do not count restricted data even if a click blocks it. A changed source between summary and drilldown must be visibly refreshed or marked as-of/stale, not falsely reconciled. QWeb/CSV/XLSX respects source record rules, restricted attachments and party audience; no superuser data aggregation leaks. Native Odoo features are used only after the installed Enterprise capability is verified; an unavailable widget is a clear unavailability, not silent fabrication or a second reporting engine.

**Proof:** all six report/card drilldowns; five-container/four-PO mixed join; one buyerless movement; same company/party restrictions on list, search, saved view, pivot, generated PDF and export; unknown vs zero; source revision rolled during a dashboard session; no render-time write/send/post.

## 9. Cross-module topology, amendment and recovery rules

**Intended addon dependency direction (candidate, not a verified final `__manifest__`):** `plasticos_export -> plasticos_documents_native -> plasticos_documents -> plasticos_logistics -> plasticos_transaction`, along with only actually consumed native Sale/Purchase/Stock/Mail/Enterprise addon dependencies. Verify the actual DAG and the installed exact addon names before implementation. No reverse `plasticos_logistics`, `plasticos_transaction`, `plasticos_documents` or native bridge `depends` on Export. An `_inherit` extension defined in the downstream Export addon is not a license to skip source-owner BRS/ADR adoption or create an unenforced export-only check.

**Data migration/cutover:** Only source owners migrate their existing load/transaction identities, company, historical physical container identity or document authority; Export does not bulk rewrite upstream owners. Migration preserves old IDs and exact immutable history, resolves deterministic matches, reports ambiguous/cross-company records explicitly and demonstrates replay/rollback. On installation, no fictitious booking, slot, shipment, document approval, native move, carrier email or filing is manufactured; defaults are `off` for external effects unless a later separately approved activation is proven. Do not run real-provider calls in a migration.

**Owner handoff dependencies (all NOT_ADOPTED):**

| Contract | Required accepted source owner | Prior gate | Acceptance evidence | Status |
| --- | --- | --- | --- | --- |
| `EXP-IC-01` | Purchase/Sales/Stock + Transaction scope | GAP-01, GAP-05/06 | exact order-line and physical quantity witness, no double fulfillment | NOT_ADOPTED / NOT_RUN |
| `EXP-IC-02` | Logistics/Transaction/actual physical owner | GAP-01/02 | exact company/load, buyerless, ISO-versus-package, old-link migration | NOT_ADOPTED / NOT_RUN |
| `EXP-IC-03` | Export booking owner + native line/physical owners | GAP-02/05 | lock/revision/concurrency, no stock write | NOT_ADOPTED / NOT_RUN |
| `EXP-IC-04` | PlasticOS Documents + native Documents bridge | GAP-03/06 | one original, typed links, sole verifier, Enterprise rights | NOT_ADOPTED / NOT_RUN |
| `EXP-IC-05` | Logistics + Export read-only context owner | GAP-01/02/04 | source-revision guard on every physical release path | NOT_ADOPTED / NOT_RUN |
| `EXP-IC-06` | Logistics/Linda + native Mail | GAP-04 | booking obligation without source-order counterfeit, no unknown resend | NOT_ADOPTED / NOT_RUN |
| `EXP-IC-07` | Export presentation + underlying native owner/Enterprise platform | GAP-05/06 | six grains and same-scope drilldown plus permission test | NOT_ADOPTED / NOT_RUN |

**Concrete sequence recommendation:** First settle `EXP-IC-02` exact physical shipment identity and company, coupled to `EXP-IC-01` actual source identity. Then accept `EXP-IC-03` capacity linkage. In parallel after exact owner review, resolve `EXP-IC-04` single verifier, `EXP-IC-05` current revision release guard and `EXP-IC-06` Linda source-kind support. Once all material source interfaces exist, finish `EXP-IC-07` reporting and Enterprise install proof. This is a **dependency order**, not a blanket merge queue or permission to edit code.

## 10. Adversarial integration acceptance: owner-positive and owner-negative

`IC-Txx` are new grouping witnesses, **not** replacements or altered text for the 120 `AC-EXP-*` cases. Status of every witness below is `NOT_RUN`; test labels are not claimed to exist in Git or a CI suite. Positive and negative are both required before declaring an interface accepted.

| Witness | Positive proof | Negative falsifier | Contract / original acceptance links |
| --- | --- | --- | --- |
| IC-T01 | 30-load SO, four-load PO, four exact shipment executions without duplicated orders; actual Stock balances reconcile | fourth load replaces first; whole SO marked fulfilled | IC-01/02; AC-EXP-02-001, AC-EXP-08-002..006 |
| IC-T02 | PO-only warehouse receipt and buyerless sourced movement have real company and valid native authority | creates fake SO/buyer/load or loses company | IC-01/02; AC-EXP-08-001, AC-EXP-08-008 |
| IC-T03 | one booking, five ISO equipment journeys from four POs, with true source provenance | 5 x 4 = 20 journeys or packaging count used as ISO | IC-02/03; AC-EXP-13-005, AC-EXP-14-015 |
| IC-T04 | one slot holds two actual PO source lines yet occupies one capacity slot | second line increments booked capacity | IC-03; AC-EXP-14-014..016 |
| IC-T05 | two concurrent attempts for last slot yield at most one committed outcome | both commits succeed or stale revision succeeds | IC-03; AC-EXP-14-016 |
| IC-T06 | booking drops 5 to 4 while five units are committed; historic units retained, overallocated reported | automatically deletes loaded unit or reopens shipped capacity | IC-03/05; AC-EXP-14-014, AC-EXP-14-016 |
| IC-T07 | real physical ISO number can occur in a later independently sourced voyage with new journey identity/seal | global number uniqueness blocks legal reuse or merges journeys | IC-02; AC-EXP-07-004, AC-EXP-13-005 |
| IC-T08 | one native original supports two exact verified obligations independently and without copied bytes | native and PlasticOS verify independently or one supersession clears both without reason | IC-04; AC-EXP-03-001..003 |
| IC-T09 | four same-partner weekly source notices yield exact matches or explicit review | newest-open-transaction auto-link accepted | IC-04; AC-EXP-09-003, AC-EXP-11-003 |
| IC-T10 | AI source extraction is candidate until authorized domain acceptance; booking fact distinct from document verification | OCR sets verified/dispatch/invoicing or newest attachment inherits older approval | IC-04; AC-EXP-09-002, AC-EXP-09-006..007 |
| IC-T11 | one rolled cutoff affects only week-three pending freight/packet, retains weeks 1/2/4 and sent history | blanket cancellation, automatic rate award, queued stale packet sent | IC-05/06; AC-EXP-10-004, AC-EXP-11-011 |
| IC-T12 | timezone-ambiguous carrier cutoff is review/block only for exact dependent move; pickup date and ERD distinct | guesses DST offset, treats cutoff as pickup time, blocks all domestic | IC-05; AC-EXP-02-003..004, AC-EXP-10-005 |
| IC-T13 | approved PO sent before booking; separate booking intent later; same PO never reissued just because 4 weekly bookings exist | Linda request falsified with PO/SO placeholder or four duplicate PO emails | IC-06; AC-EXP-10-002 |
| IC-T14 | native Mail returns unknown outcome, Linda reconciles before resend; cancellation ordered by recipient/cycle | repeat send on timeout or sent evidence overwritten on roll | IC-06; AC-EXP-03-005, AC-EXP-10-004 |
| IC-T15 | actual supplier-delivered FAS and ordinary domestic path remain operable without made-up drayage booking | export packet required for every supplier delivery or domestic transition | IC-02/05/06; AC-EXP-04-002, AC-EXP-10-008 |
| IC-T16 | six report summaries and links are same-grain, same-filter and company/party scoped; 5 actual containers remain 5 | cross-company count/download, unfiltered drilldown, 20 containers after join | IC-07; AC-EXP-14-002, AC-EXP-14-012, AC-EXP-14-022 |
| IC-T17 | clean Enterprise install/upgrade, replay and source-revision recovery with no external effects | Community-only green claimed Enterprise proof, real mail on install, duplicate booking on replay | IC-01..07; AC-EXP-01-005, AC-EXP-06-005 |

## 11. Owner decisions that remain bounded and unresolved

These are **implementation-owner placement decisions**, not requests to reopen already frozen Export business semantics. Do not fabricate an owner acceptance simply because this file names a proposed solution.

1. **Logistics/Transaction exact link:** choose the smallest current-source representation and deterministic historical link migration that removes first-by-SO and supports a company independently of an SO, without changing the meaning of the existing valid transaction/load link.
2. **Actual ISO container journey owner:** determine whether verified Stock/package/load fields already represent ISO identity + journey + seal; only then decide whether an owner-local extension is irreducible. `plasticos.equipment.type` (facility machinery) is not the freight container vocabulary.
3. **Documents native bridge:** pick the single authoritative verified decision path and an exact many-link original representation; prove installed native behavior and do not trust `get_missing_documents(..., purpose="export")` until an actual accepted Documents interface exists.
4. **Linda:** accept a booking-origin source-kind and audience/revision identity under existing Linda-owned one-outbound-intent semantics. Current SQL CHECK is not extensible by simply adding another `purpose` enum value.
5. **Logistics export constraint hook:** choose a source-owner-approved, all-path enforced, acyclic Odoo addon extension. Do not assume a new hook or callback already exists.
6. **Installed Enterprise closure:** verify Documents, Mail, Stock, QWeb, native dashboard/spreadsheet and ACL APIs in an isolated Odoo 19 Enterprise registry before creating a final manifest or asserting addon readiness.

**Phase 2 is outside these adoption decisions:** optional FindTEU observed milestones and AESDirect authorized filing preparation/handoff remain separate future source-owner contracts, not hidden prerequisites to Phase 1.

## 12. Source anchors and explicit assurance limits

All source anchors are **observations**, not accepted owner implementations:

| Observation | Exact pinned source |
| --- | --- |
| Sale-order-derived load company and first-by-SO transaction auto-link | [`plasticos_logistics/models/load.py` L43-46, L257-298](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/load.py#L257-L298) |
| Universal buyer requirement with unique transaction/load association | [`plasticos_logistics/models/transaction_inherit.py` L8-62](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/transaction_inherit.py#L8-L62) |
| Legacy `container_no` may mean packaging rather than physical ISO identity | [`plasticos_transaction/models/transaction_line.py` L98-124](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_transaction/models/transaction_line.py#L98-L124) |
| Current freight context hardcodes equipment class unknown | [`plasticos_logistics/services/freight_context.py` L71-80](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/services/freight_context.py#L71-L80) |
| Two document verification actions, partner-recency native auto-link | [`plasticos_documents/models/document.py` L165-185](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/models/document.py#L165-L185), [`plasticos_documents_native/models/document_native.py` L118-175](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents_native/models/document_native.py#L118-L175) |
| Existing compliance service only recognizes invoice and close purposes | [`plasticos_documents/models/compliance_service.py` L12-64](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/models/compliance_service.py#L12-L64) |
| Linda currently requires exact PO/SO, SQL constraint excludes booking-origin request | [`plasticos_logistics/models/linda_request.py` L153-279](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/linda_request.py#L153-L279) |
| Linda PO/SO queues are outcome-tracked, not guaranteed delivered | [`plasticos_logistics/models/linda_request.py` L585-680](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/models/linda_request.py#L585-L680) |
| Facility equipment model is plant production equipment, not ocean slots | [`plasticos_facility_profile/models/equipment_type.py` L5-32](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_facility_profile/models/equipment_type.py#L5-L32) |
| Existing Logistics and Documents BRS ownership and supersession | [`plasticos_logistics/business_rules/README.md`](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_logistics/business_rules/README.md), [`plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md`](https://github.com/cryptoxdog/IB-Odoo_19/blob/04bd0594a7c9dcad53d9c45fc65276d76817c112/plasticos_documents/business_rules/OWNERSHIP_AND_INTEROP.md) |

**GAR disposition:** read-only source-backed, bounded *candidate interface synthesis*. Current source owner adoption and Enterprise runtime tests are NOT_RUN; independent specialist challenge, validated canonical GAR projection and formal GARReceipt are not represented as PASS. A new source finding that contradicts this interface requires revision-bound owner review, not a workaround. Nothing here grants an agent code, migration, publication, mail, filing or deployment permission.
