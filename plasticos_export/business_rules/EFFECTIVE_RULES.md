# Export BRS | exact effective rules

**Origin:** Export BRS v2.0.0 (`rules.json`). **Status:** module-owned baseline; admission on authorized merge, not before. All runtime outcomes NOT_RUN.

This file renders the exact `statement` of every rule from `rules.json`; no text is rewritten. The source pack already folds the v1.2 to v1.9 supersessions into those statements (see `SUPERSESSION.md`). Phase `P2` rules stay in force as requirements but are outside the Phase 1 campaign.

## BRS-EXP-01 — Native-first boundaries and minimality

### BRS-EXP-01-R001 — Thin export scope
**LOCKED** · **BOTH** · **Owner:** plasticos_export

`plasticos_export` SHALL own only the missing export-specific booking/shipment context, applicability declarations, views and QWeb report layouts; it SHALL first inspect and reuse existing Odoo/PlasticOS records and SHALL NOT recreate storage, a logistics/dispatch engine, inventory, finance, or a shared document-compliance engine.

Acceptance: AC-EXP-01-001 · Runtime: **NOT_RUN**

### BRS-EXP-01-R002 — Single authoritative fact owner
**LOCKED** · **BOTH** · **Owner:** existing native and domain owners

Original bytes/versions belong to native Odoo Documents or approved `ir.attachment` fallback; business evidence classification/verification belong to `plasticos_documents`; purchase/sales and financial facts belong to native Odoo; stock movements belong to native Stock; freight, dispatch and approved external operational mail belong to `plasticos_logistics`/Linda. Export SHALL only bind and display those facts.

Acceptance: AC-EXP-01-002 · Runtime: **NOT_RUN**

### BRS-EXP-01-R003 — Exact associations without mandatory early buyer
**LOCKED** · **BOTH** · **Owner:** Export binding; native commercial owners

All export bookings, sale/purchase order lines, loads, documents, packages and containers SHALL be linked by exact company and typed identity, not guessed partner/name/newest record. A supplier-backed load or owned in-transit inventory MAY have no assigned buyer or sales order until a real sale occurs, subject to the approved procurement/movement authority. An actual customer sale SHALL retain its real buyer. No artificial buyer, sales order, transaction or stock picking SHALL be created merely to satisfy a foreign-key or dispatch constraint.

Acceptance: AC-EXP-01-003 · Runtime: **NOT_RUN**

### BRS-EXP-01-R004 — Evidence proposals are not unauthorized business transitions
**LOCKED** · **BOTH** · **Owner:** native state owner; authorized tool command

Saving or extracting a booking, receiving a file, scanning, or generating a report SHALL NOT directly set a purchase, sale, transaction, stock, load, compliance, financial or regulatory state. A verified source observation MAY request a *named, authorized* state-owner business action if exact scope, preconditions, idempotency, and actor permissions are satisfied. The authoritative owner SHALL enforce the transition and return accepted/refused with reason and provenance; no direct state write or bypass is allowed.

Acceptance: AC-EXP-01-004 · Runtime: **NOT_RUN**

### BRS-EXP-01-R005 — Capability proof and deployment independence
**DESIGN** · **BOTH** · **Owner:** Odoo deployment/license owner

Before depending on Enterprise Documents, Inventory Barcode, AI/OCR or IoT device features, installation, licensing and actual installed API SHALL be verified; where the approved build lacks a capability, Export SHALL use an explicitly approved native fallback or keep it unavailable rather than fabricate or silently require it.

Acceptance: AC-EXP-01-005 · Runtime: **NOT_RUN**

## BRS-EXP-02 — Booking identity, six fields and schedule evidence

### BRS-EXP-02-R001 — Booking-to-order and shipment cardinality independent
**DESIGN** · **BOTH** · **Owner:** plasticos_export booking association; native commercial and Logistics identities

A booking SHALL have an authoritative typed company and revision context and MAY relate to one or more physical containers/movements according to the real carrier reservation. One Sales Order or Purchase Order MAY be fulfilled by many loads and distinct bookings; a physical shipment SHALL be linked to its applicable booking and exact order-line/fulfillment allocation without requiring the entire SO or PO to be one shipment. The booking, drayage load, ISO container, seal, stock package/lot and order remain separate identities. A new booking model is conditional on reuse evidence.

Acceptance: AC-EXP-02-001 · Runtime: **NOT_RUN**

### BRS-EXP-02-R002 — Six first-class booking values
**LOCKED** · **BOTH** · **Owner:** plasticos_export for gaps only

Booking No., Steamship Line, Port of Loading, Port of Discharge, Cut Off and Earliest Return Date SHALL be first-class searchable/displayable booking information when supplied; existing authoritative fields SHALL be reused before creating storage. Booking No. remains an unmodified string; Steamship Line SHALL be distinct from forwarder and drayage carrier; POL/POD SHALL be distinct from terminal, rail ramp and final destination.

Acceptance: AC-EXP-02-002 · Runtime: **NOT_RUN**

### BRS-EXP-02-R003 — ERD and cargo cutoff semantics
**LOCKED** · **BOTH** · **Owner:** plasticos_export schedule context

Earliest Return Date SHALL represent the effective earliest permitted loaded-container receiving/gate-in window for the stated booking and facility; Cut Off SHALL represent its stated cargo/terminal acceptance deadline. ERD, cargo cutoff, shipping-instruction cutoff, VGM cutoff, documentation, rail and filing deadlines SHALL remain distinct. A booking without a supplied timestamp SHALL remain date-only or unknown, without invented time-of-day.

Acceptance: AC-EXP-02-003 · Runtime: **NOT_RUN**

### BRS-EXP-02-R004 — Schedule source, revisions and time zones
**DESIGN** · **BOTH** · **Owner:** plasticos_export schedule context + native document provenance

Each booking schedule assertion SHALL retain exact source/original reference, reporter, observed time, terminal/local time zone, value precision, effective revision and supersession. A later email SHALL NOT silently overwrite a confirmed cutoff/ERD, and conflicting carrier/terminal notices SHALL remain visible until the responsible party resolves them.

Acceptance: AC-EXP-02-004 · Runtime: **NOT_RUN**

### BRS-EXP-02-R005 — Operational readiness is a projection
**DESIGN** · **BOTH** · **Owner:** plasticos_export view/exception projection

Export schedule and readiness views SHALL derive status from current booking evidence, native load/stock status and verified document applicability without becoming a second source of physical or regulatory state. A schedule conflict, missing applicable proof or expired acceptance window SHALL produce an attributed exception; an observed gate event is not automatically legal delivery/risk transfer.

Acceptance: AC-EXP-02-005 · Runtime: **NOT_RUN**

### BRS-EXP-02-R006 — Commercial label is not a legal Incoterm
**LOCKED** · **BOTH** · **Owner:** native Odoo order/contract + export display

The recycler trade labels `FOB` (buyer pickup), `FAS` (seller-included freight to agreed port/rail), and `CNF`/`C&F` SHALL be preserved as quoted business usage separately from any explicitly contracted formal ICC Incoterm and named place. Booking arranger, payer, contracted handoff and exporter/filing role SHALL be explicit facts, not inferred from either shorthand. Export SHALL never silently rewrite an order Incoterm.

Acceptance: AC-EXP-02-006 · Runtime: **NOT_RUN**

## BRS-EXP-03 — Document applicability, evidence and reporting

### BRS-EXP-03-R001 — Native intake, AI-proposed extraction and exact document attribution
**LOCKED** · **BOTH** · **Owner:** native Documents intake; plasticos_documents exact evidence link

Booking confirmations, amendments, gate receipts, emails and other originals SHALL enter through native Documents/approved attachments and retain original bytes, versions and attributable metadata. Odoo 19 AI document facilities MAY extract proposed typed booking values and candidate relations, but SHALL NOT auto-commit a partner-only or newest-open-record guess. The document owner SHALL resolve the exact company, booking, intended physical shipment and valid revision (or hold for review) before Export consumes facts; no duplicate original store or verifier.

Acceptance: AC-EXP-03-001 · Runtime: **NOT_RUN**

### BRS-EXP-03-R002 — Applicability belongs to export, verdict to Documents
**LOCKED** · **BOTH** · **Owner:** export applicability / `plasticos_documents` verification

Export SHALL declare which document categories are required for the specific booking, phase, agreement, party, stage and requested operation. `plasticos_documents` SHALL own whether exact current evidence meets those requirements and whether an authorized override applies. Export SHALL consume that verdict, never author its own verified/compliant status or second rule evaluator.

Acceptance: AC-EXP-03-002 · Runtime: **NOT_RUN**

### BRS-EXP-03-R003 — No duplicate verification action
**LOCKED** · **BOTH** · **Owner:** `plasticos_documents`

Native Documents UI/actions SHALL delegate business verification, refusal and override to one approved `plasticos_documents` owner with attributable actor, source/version and scope; Export SHALL be read-only for the verification result. Existing duplicated native `verified` actions SHALL be reconciled at the Documents owner before Export relies on their output.

Acceptance: AC-EXP-03-003 · Runtime: **NOT_RUN**

### BRS-EXP-03-R004 — Native export-specific reports
**LOCKED** · **BOTH** · **Owner:** plasticos_export QWeb layout / native source values

Export MAY own only export-specific QWeb report templates and view composition (booking/dispatch sheet, container/package packing list, exceptions, outbound document packet). Data SHALL come from the current native sales, stock, logistics, booking and verified Documents owners; reports SHALL be version-aware, audience-safe and shall not impersonate a third-party issued B/L or certification.

Acceptance: AC-EXP-03-004 · Runtime: **NOT_RUN**

### BRS-EXP-03-R005 — Linda owns external sends
**LOCKED** · **BOTH** · **Owner:** `plasticos_logistics` / Linda using native Odoo Mail

An export screen MAY request an authorized outgoing report, booking reply, document request or amendment through the approved existing Linda/Odoo Mail operation. Export SHALL NOT send, retry, chase, or separately schedule the same external correspondence; queued, sent and unknown delivery outcomes SHALL remain distinct and attributable.

Acceptance: AC-EXP-03-005 · Runtime: **NOT_RUN**

### BRS-EXP-03-R006 — Missing documents use existing activity owners
**DESIGN** · **BOTH** · **Owner:** `plasticos_documents`/native Activity; Linda external reminders

A missing or invalid export-required file SHALL appear as one scoped Documents compliance exception and the appropriate native internal Activity/Request; any approved external chase uses the existing Linda obligation and native scheduler. Export SHALL NOT add a recurring document-chase cron or another reminder ledger.

Acceptance: AC-EXP-03-006 · Runtime: **NOT_RUN**

### BRS-EXP-03-R007 — Correct document type and actual obligation
**DESIGN** · **BOTH** · **Owner:** export applicability / document type owner

The required file set SHALL depend on actual booking, cargo, contract, destination/transit jurisdiction and responsible party; Phase 1 shall not require every Phase 2 ocean document. Domestic truck BOL, carrier-issued ocean B/L, verified gross mass evidence, commercial invoice and filings SHALL be separately classified and attributed; a file received is not a valid approval merely by existing.

Acceptance: AC-EXP-03-007 · Runtime: **NOT_RUN**

## BRS-EXP-04 — Phase 1: recycler FOB pickup and FAS port/rail

### BRS-EXP-04-R001 — FOB buyer pickup as industry operation
**LOCKED** · **P1** · **Owner:** commercial order + `plasticos_logistics`

Phase 1 SHALL support `FOB pickup` in the operator’s recycling trade meaning: buyer/agent arranges pickup at the agreed origin. Export MAY display linked booking evidence when supplied but SHALL NOT require ocean booking data or seller-arranged freight for every FOB pickup. Pickup, carrier and physical dispatch remain existing logistics/stock operations.

Acceptance: AC-EXP-04-001 · Runtime: **NOT_RUN**

### BRS-EXP-04-R002 — FAS inland freight-included delivery
**LOCKED** · **P1** · **Owner:** commercial order + `plasticos_logistics`

Phase 1 SHALL support `FAS delivered port/rail` in the operator’s established recycling trade meaning: seller includes the agreed inland transportation to the identified port/rail destination. It SHALL expose booking details and timing when relevant, reusing existing carrier/freight/load authority; it SHALL NOT infer seller ocean freight or substitute the formal ICC FAS risk-transfer point.

Acceptance: AC-EXP-04-002 · Runtime: **NOT_RUN**

### BRS-EXP-04-R003 — Physical handoff and commercial allocation are independent
**DESIGN** · **P1** · **Owner:** Logistics and native Stock; Documents verification; Export projection

Each Phase 1 movement SHALL preserve actual pickup, gate/rail acceptance, named handoff place and source evidence independently of whether a buyer is already allocated. An owned supplier-backed movement with no assigned buyer is an eligible commercial scenario only when its separate authorization and destination/booking requirements are satisfied. Sale order fulfillment or invoicing may occur later under its own native authority; terminal arrival, gate acceptance and legal transfer are distinct.

Acceptance: AC-EXP-04-003 · Runtime: **NOT_RUN**

### BRS-EXP-04-R004 — ERD-to-cutoff dispatch visibility
**DESIGN** · **P1** · **Owner:** export schedule view + Linda

Where a live booking or terminal appointment exists, Phase 1 SHALL present its current sourced ERD/cargo cutoff window and risk exception to the responsible coordinator. Changes SHALL not independently modify a Linda commitment, dispatch, or send an amendment; these are coordinated through the existing owner.

Acceptance: AC-EXP-04-004 · Runtime: **NOT_RUN**

### BRS-EXP-04-R005 — Native documents and simple views first
**LOCKED** · **P1** · **Owner:** `plasticos_export` views/report layout

The Phase 1 export UI SHALL prioritize a booking/shipment list/form, ERD and cargo cutoff visibility, missing-evidence exceptions, a linked document view and a small set of native export reports. A dedicated new export workflow engine or complex overseas tracking UI is out of scope.

Acceptance: AC-EXP-04-005 · Runtime: **NOT_RUN**

## BRS-EXP-05 — Phase 2: international sale and ocean obligations

### BRS-EXP-05-R001 — In-transit sale reuses original shipment and evidence
**LOCKED** · **P2** · **Owner:** native commercial sale and inventory owner; Export link/projection

Phase 2 SHALL support a genuine buyer purchasing material already on the water, including later sale-order allocation to existing identified cargo while preserving original purchase, container, booking, stock custody, delivery, and documents. The seller/buyer, title terms, Incoterm, approval and pricing SHALL be governed by the real native commercial owner and contract. No new parallel shipment/stock ledger or retroactive falsification of historic transport facts is permitted.

Acceptance: AC-EXP-05-001 · Runtime: **NOT_RUN**

### BRS-EXP-05-R002 — Freight-inclusive price/role semantics
**LOCKED** · **P2** · **Owner:** native commercial order + `plasticos_logistics`

Phase 2 SHALL support recycler `CNF/C&F` trade shorthand, and explicit contractual CFR/CIF terms where agreed, while preserving booking arranger, freight payer, ocean carrier/forwarder, insurer when applicable, seller obligations and agreed destination separately. Freight quotes/actuals remain with existing logistics/accounting owners; terms SHALL NOT alone infer title transfer or risk at destination.

Acceptance: AC-EXP-05-002 · Runtime: **NOT_RUN**

### BRS-EXP-05-R003 — Ocean milestones are sourced facts
**DESIGN** · **P2** · **Owner:** `plasticos_export` contextual projection / third-party evidence

Phase 2 MAY expose verified vessel/voyage, container loading, port departure, discharge, delivery and exception information where carrier/forwarder data is actually supplied; each observation SHALL retain source and revision, and SHALL NOT overwrite native stock, freight or customer delivery authority.

Acceptance: AC-EXP-05-003 · Runtime: **NOT_RUN**

### BRS-EXP-05-R004 — Ocean B/L, shipping instructions and VGM
**DESIGN** · **P2** · **Owner:** native Documents + document compliance + export applicability

Phase 2 SHALL coordinate applicable shipping instructions, issued ocean B/L (carrier/forwarder original), required VGM evidence and export packet documents using native original custody and shared verification. Export SHALL NOT forge or issue a carrier B/L, assert VGM compliance from package-net sum alone, or add a separate document verifier.

Acceptance: AC-EXP-05-004 · Runtime: **NOT_RUN**

### BRS-EXP-05-R005 — Applicable regulated filings and filing actors
**DESIGN** · **P2** · **Owner:** external filing authority + native Documents evidence

Where material, destination, transit, and law require export filings, permits, consents or jurisdiction-specific documents, Phase 2 SHALL record the applicable decision, responsible exporter/filer, authority and evidence/status with explicit attribution. It SHALL NOT auto-approve material legality, submit AES/customs filings or claim a compliance clearance without authorized integration and verified real result.

Acceptance: AC-EXP-05-005 · Runtime: **NOT_RUN**

### BRS-EXP-05-R006 — Phase 2 operations remain native-first
**LOCKED** · **P2** · **Owner:** native Odoo + Linda + Documents

Export SHALL reuse native multi-currency orders, accounting, payments, stock, existing freight/dispatch and document operations for international selling; destination-milestone and report requirements SHALL not cause duplicate finance, carrier mail, scheduler, stock or new payment state machine.

Acceptance: AC-EXP-05-006 · Runtime: **NOT_RUN**

## BRS-EXP-06 — Security, exceptions, readiness and acceptance

### BRS-EXP-06-R001 — Audience/confidentiality and company isolation
**LOCKED** · **BOTH** · **Owner:** native Odoo ACLs + Documents/Linda owners

Every booking, document link, generated report, outgoing recipient and related stock/order lookup SHALL enforce the exact company and approved audience. Supplier economics, buyer identity, freight economics and sensitive documents SHALL NOT leak across a brokered trade or company boundary; Export SHALL not grant external Documents access.

Acceptance: AC-EXP-06-001 · Runtime: **NOT_RUN**

### BRS-EXP-06-R002 — Unknown and contradictory evidence remains visible
**LOCKED** · **BOTH** · **Owner:** export projections with source owner decisions

Missing, wrong-party, stale, superseded, conflicted or uncertain export evidence SHALL remain UNKNOWN/pending with an attributed exception. Export SHALL NOT use fuzzy linking, optimistic defaults or AI/OCR inferences to declare a validated booking, shipment, compliant document, gate acceptance or regulatory result.

Acceptance: AC-EXP-06-002 · Runtime: **NOT_RUN**

### BRS-EXP-06-R003 — Order, shipment, evidence and transaction states remain scoped
**LOCKED** · **BOTH** · **Owner:** native commercial/state owners; Export read-only projection

Purchase/Sale ordered quantity, each physical receipt/dispatch, each booking/terminal milestone, document verification, transaction state, invoicing and financial settlement SHALL remain independent and scoped to the correct child/line. One of four weekly loads delivered SHALL NOT mark the entire four-load PO fulfilled nor a 30-load SO delivered. AI may propose a transition but the existing validated state owner SHALL apply it only if the explicitly required evidence, quantities and authorization permit it.

Acceptance: AC-EXP-06-003 · Runtime: **NOT_RUN**

### BRS-EXP-06-R004 — Minimality and acceptance gate
**DESIGN** · **BOTH** · **Owner:** product owner/repository implementation owner

A future proposed export field, model, menu, QWeb report, cron or automation SHALL carry a source-owner census, a concrete unmet business action and one positive plus one failure acceptance case. Rules are planning requirements until separately admitted and implemented. Each real test SHALL cite its BRS ID, exact repo revision and observed evidence; no unrun scenario may be labeled PASS.

Acceptance: AC-EXP-06-004 · Runtime: **NOT_RUN**

### BRS-EXP-06-R005 — Safe change and activation boundaries
**LOCKED** · **BOTH** · **Owner:** operator + live owner of each capability

The export BRS pack SHALL not itself install a module, activate mail or cron, create shipment transactions, approve legal filings or change Native-First BRS semantics. Any implementation/cutover requires a bounded separately authorized contract; changes to prior locked decisions require explicit dated supersession, preserving old rules and acceptance trace.

Acceptance: AC-EXP-06-005 · Runtime: **NOT_RUN**

## BRS-EXP-07 — Transport equipment types, booking quantities and container identity

### BRS-EXP-07-R001 — Equipment vocabulary differentiates road trailers from ocean containers
**LOCKED** · **BOTH** · **Owner:** Logistics transport equipment classification; Export uses scoped choices

The transport equipment selections SHALL distinguish domestic road trailers from maritime freight containers. It SHALL NOT conflate vehicle/trailer identity, ISO container identity, shipping booking identity, Odoo stock package identity, or an internal load. A chassis carrying an ocean container remains a ground transport leg associated with a distinct maritime container.

Acceptance: AC-EXP-07-001 · Runtime: **NOT_RUN**

### BRS-EXP-07-R002 — Supported domestic trailer choices
**LOCKED** · **P1** · **Owner:** Logistics transport equipment; Export references for terminal drayage if applicable

Domestic dispatch SHALL support 53-foot trailers, 48-foot trailers and flatbeds. Flatbeds SHALL be a type independent of any assumed universal length; dimensions and restrictions MAY be specified for the actual move. Export SHALL NOT create a second domestic trailer catalog or dispatch process.

Acceptance: AC-EXP-07-002 · Runtime: **NOT_RUN**

### BRS-EXP-07-R003 — Supported ocean container choices with a preference, not a hard constraint
**LOCKED** · **BOTH** · **Owner:** Export booking presentation; shared logistics equipment semantics

Export booking choices SHALL include 40-foot high cube (40HC), 40-foot standard (40STD), 45-foot high cube (45HC), 45-foot standard (45STD) and 20-foot standard (20STD). For the operator's plastic exports, 40HC SHALL be the default suggested option, not an enforced selection. 20STD SHALL remain selectable for metal recyclers without precluding other cargo. Supported-in-UI does not assert steamship-line, route, port, or chassis availability.

Acceptance: AC-EXP-07-003 · Runtime: **NOT_RUN**

### BRS-EXP-07-R004 — Booking equipment count and per-week physical units
**DESIGN** · **BOTH** · **Owner:** Export reservation; Logistics actual movements; native Stock cargo

A booking SHALL capture requested container equipment and count; physical units SHALL separately retain ISO number, seal, actual equipment, native stock packages and linked movement/load identity. Several containers MAY share one booking; distinct weekly movements MAY each have their own booking even when they share one PO and SO. Requested/actual equipment amendments SHALL not overwrite other siblings or invent copy-per-unit cargo weight.

Acceptance: AC-EXP-07-004 · Runtime: **NOT_RUN**

### BRS-EXP-07-R005 — Reuse only the correct equipment owner and native records
**DESIGN** · **BOTH** · **Owner:** Logistics transport master/native shipping record; Export only booking-specific fields

Before adding any transport-type persistence, inspect native Odoo delivery/shipping and existing PlasticOS Logistics fields and extend the canonical owner only for an actual gap. `plasticos.equipment.type` is an existing FACILITY production/handling equipment registry (balers, granulators, etc.) and SHALL NOT be repurposed as a freight-container type registry. `plasticos_export` SHALL NOT create a competing universal equipment master, stock package, carrier record or transport engine.

Acceptance: AC-EXP-07-005 · Runtime: **NOT_RUN**

### BRS-EXP-07-R006 — Do not infer payload, capacity or VGM from nominal equipment name
**DESIGN** · **BOTH** · **Owner:** Physical weight: native Odoo Stock and verified scale evidence; Export displays source facts

Equipment labels SHALL NOT imply a fixed cargo limit or certified legal weight. Actual scale observations, package net/tare, container tare, gross, lashing/packing weight where applicable, local carrier/road/port constraints, and any valid VGM evidence SHALL retain their respective sources, units, revisions and verification. Export SHALL NOT derive a certified VGM or commercial settlement quantity solely from scanned package weights or from a 40HC/20STD selection.

Acceptance: AC-EXP-07-006 · Runtime: **NOT_RUN**

### BRS-EXP-07-R007 — Equipment discrepancy and booking amendment are explicit
**DESIGN** · **BOTH** · **Owner:** Export booking contextual exception; Documents evidence; Logistics physical movements

A mismatch between requested and supplied equipment SHALL be reported with provenance and require an authorized booking amendment or explicit exception resolution. Confirmed equipment type and actual container ID SHALL follow physical evidence. Export SHALL not rebook, dispatch, email the carrier, change stock, change the Incoterm or cancel a booking merely because an equipment selection changes.

Acceptance: AC-EXP-07-007 · Runtime: **NOT_RUN**

### BRS-EXP-07-R008 — Reports and loading must use exact units without duplicate inventory
**DESIGN** · **BOTH** · **Owner:** Export views/QWeb; native Stock physical movement; Documents evidence/verification

Booking screens, loading/packing reports and associated documents SHALL display requested equipment, confirmed equipment, count and each actual container ID/seal as available, sourced from their owner. QR scans SHALL continue to update native Odoo stock/package movements and per-container loading evidence, not an export-owned inventory ledger. Blank/unconfirmed equipment or ambiguous load association SHALL display Unknown/Needs Review instead of inventing capacity, seal or departure status.

Acceptance: AC-EXP-07-008 · Runtime: **NOT_RUN**

## BRS-EXP-08 — Multi-order commitments, partial fulfillment, buyer-optional cargo and allocation

### BRS-EXP-08-R001 — Buyer optional before a genuine sale
**LOCKED** · **BOTH** · **Owner:** native Purchase/Stock + permitted Logistics movement authority

A purchase, real owned material, or authorized physical export movement MAY be recorded and progressed without a buyer, customer SO, or assigned end buyer when no sale exists. Supplier, company, approval, stock/custody, movement purpose, destination and applicable booking shall be real; buyer-dependent rules still apply to actual customer-sale release. No fake buyer/order or implied sale shall be used to bypass validation.

Acceptance: AC-EXP-08-001 · Runtime: **NOT_RUN**

### BRS-EXP-08-R002 — One large customer commitment with smaller supply orders
**LOCKED** · **BOTH** · **Owner:** native `sale.order`/`purchase.order` lines

One real buyer commitment (example: customer PO represented by one SO for 30 MRP loads) SHALL be fulfillable through multiple suppliers, supplier POs, and physical shipments. A supplier PO for 4 loads SHALL coexist with that 30-load SO without requiring four separate supplier POs; customer PO evidence is not a supplier PO.

Acceptance: AC-EXP-08-002 · Runtime: **NOT_RUN**

### BRS-EXP-08-R003 — Partial purchase fulfillment without PO duplication
**LOCKED** · **BOTH** · **Owner:** native Odoo Purchase and Stock receipt/picking owner

A supplier PO MAY authorize multiple separately ready and executed loads across weeks. Native receipt/backorder and delivered/remaining quantity mechanics SHALL be used for each physically executed quantity; the PO obligation remains open for its unfulfilled balance. No Export-created parallel purchase/receipt counters.

Acceptance: AC-EXP-08-003 · Runtime: **NOT_RUN**

### BRS-EXP-08-R004 — Partial sales fulfillment and reserved allocation
**LOCKED** · **BOTH** · **Owner:** native Odoo Sales and Stock delivery/move lines

A customer SO MAY be fulfilled by multiple suppliers and many loads; native reserved/delivered/unfulfilled quantities SHALL remain authoritative per order line and valid UoM. If a buyer is not yet assigned, cargo remains unallocated to a sale until real contract approval. A shipment association SHALL NOT alone validate its stock picking.

Acceptance: AC-EXP-08-004 · Runtime: **NOT_RUN**

### BRS-EXP-08-R005 — Independent booking per execution and container cardinality
**LOCKED** · **BOTH** · **Owner:** Export booking and Logistics exact shipment links

One PO/SO may correspond to many bookings and loads; a single booking may cover multiple physical containers. A shipment SHALL identify its exact booking revision; no global one-to-one order-booking rule or single `transaction.load_id` may be used as the only association for a multi-load order. Define the smallest source-owned many-side association after a full cardinality census.

Acceptance: AC-EXP-08-005 · Runtime: **NOT_RUN**

### BRS-EXP-08-R006 — Fulfillment allocation is traceable without second quantity ledger
**DESIGN** · **BOTH** · **Owner:** native Stock/Purchase/Sales actual lines; Export typed linkage

When a real order spans shipments or cargo is resold in transit, maintain exact links and quantities between the participating native PO/SO order lines, pickings/moves, shipment/load, container and applicable booking. No allocation may exceed authoritative available/contracted quantities; corrections, splits and reversals SHALL be attributed and must prevent double allocation.

Acceptance: AC-EXP-08-006 · Runtime: **NOT_RUN**

### BRS-EXP-08-R007 — Late buyer assignment and on-water resale
**LOCKED** · **BOTH** · **Owner:** native commercial owner; stock custody; Export historic association

Buyer allocation MAY occur after pickup, terminal delivery or ocean sailing when a legal sale is entered and approved. The exact cargo/container/booking remains unchanged; the new sale association retains effective timestamps, actor, source contract, company and audit history. Change of physical destination or regulatory party requires independent logistics/filing authority and cannot be inferred from buyer allocation.

Acceptance: AC-EXP-08-007 · Runtime: **NOT_RUN**

### BRS-EXP-08-R008 — Movement eligibility by purpose, not a universal buyer predicate
**DESIGN** · **BOTH** · **Owner:** Logistics and native authorization owner, not Export

Movement release SHALL distinguish sale-backed delivery from approved procurement-owned/in-transit stock relocation or export drayage. Sales movements require a real buyer/SO when that workflow mandates it; lawful buyerless movements require approved company, supplier PO/owned stock authority, route/destination, cargo, applicable booking and permission. Logistics SHALL not rely on `sale_order_id` as the only possible company identity or on one transaction load field as the only exact movement link.

Acceptance: AC-EXP-08-008 · Runtime: **NOT_RUN**

## BRS-EXP-09 — Native Odoo 19 AI booking extraction, exact association and guarded transitions

### BRS-EXP-09-R001 — Use Odoo native AI Documents before custom extraction
**LOCKED** · **BOTH** · **Owner:** native Odoo Documents AI, installed capability verified

When the approved Odoo 19 Enterprise AI Documents capability is available, incoming booking confirmations and amendments SHALL be classified and candidate booking data extracted through that native facility, not a parallel Export OCR/doc ingestion engine. Actual installed APIs, AI licensing/permissions, coverage and fallback SHALL be verified before activation; if unavailable, permit controlled manual booking entry.

Acceptance: AC-EXP-09-001 · Runtime: **NOT_RUN**

### BRS-EXP-09-R002 — Typed field extraction with source-level provenance
**LOCKED** · **BOTH** · **Owner:** native AI candidate intake; export booking field owner

Native Odoo AI SHALL extract candidate values from both message body and attachments with explicit origin: purchase order reference, booking No., shipping line, POL/POD when present, ERD, terminal/cargo cutoff, equipment quantity/type, vessel/voyage, empty pickup and loaded return locations, dates, ticket, actual container/seal, reported weights and document requirements. Preserve exact strings including leading zeros, distinguishing time/date precision, reporter, field source and confidence. An absent field is UNKNOWN, never filled from a nearby attachment or assumption.

Acceptance: AC-EXP-09-002 · Runtime: **NOT_RUN**

### BRS-EXP-09-R003 — Exact company-and-booking match, never latest partner
**LOCKED** · **BOTH** · **Owner:** PlasticOS Documents exact link and Export booking lookup

Before assigning an extracted fact, resolve company, source thread, exact PO/order and applicable booking revision, shipment/load and actual physical container/ticket via corroborated typed identifiers. Multiple bookings may reference one PO; booking identity alone does not identify a physical load before container/ticket linkage. Party-only, latest-open transaction and PDF filename matches are not sufficient. A conflict or unresolved one-to-many case enters a review/exception queue without incorrect downstream writes.

Acceptance: AC-EXP-09-003 · Runtime: **NOT_RUN**

### BRS-EXP-09-R004 — Ambiguity, conflicting originals and correction review
**LOCKED** · **BOTH** · **Owner:** Documents verification owner; authorized export booking reviewer

When several candidate bookings, loads, companies, amended notices, or inconsistent ERD/cutoff fields are possible, AI SHALL abstain from authoritative writes and create a reviewable exception with candidate IDs and conflicting originals. A verified, authorized actor SHALL resolve exact linkage or reject it; the superseded/original evidence remains accessible.

Acceptance: AC-EXP-09-004 · Runtime: **NOT_RUN**

### BRS-EXP-09-R005 — Version-safe, idempotent apply
**DESIGN** · **BOTH** · **Owner:** Export booking owner; native Documents original/version keeper

Native intake SHALL deduplicate identical original document bytes and email events while retaining distinct versions even when filenames repeat. AI SHALL classify a newly observed booking-related notice as initial confirmation, same-booking revision/roll, cancellation, replacement-booking cross-reference, or supplemental capacity only when evidence suffices; otherwise retain unresolved as a proposal. Prior originals and values remain queryable. A material booking change shall trigger only exact affected downstream reassessment, never automatic carrier rebooking, blanket load cancellation or commercial PO reissue.

Acceptance: AC-EXP-09-005 · Runtime: **NOT_RUN**

### BRS-EXP-09-R006 — Apply structured values only through approved owner interface
**DESIGN** · **BOTH** · **Owner:** Export booking/record owner; Documents extraction producer

The AI component SHALL output an extraction proposal to a bounded write action that checks company, actor permission, field ownership, exact target, revision precondition and required evidence. Only fields owned by Export MAY be written there; original document classification/verification stays with Documents, transport facts with Logistics, contract values with Sales/Purchase, and stock with Inventory.

Acceptance: AC-EXP-09-006 · Runtime: **NOT_RUN**

### BRS-EXP-09-R007 — Transaction/load state changes only via validated commands
**LOCKED** · **BOTH** · **Owner:** native state transition owner (Transaction/Logistics/Stock/Accounting)

Document-derived supplier readiness, loaded shipment confirmation, carrier acknowledgment, terminal/rail acceptance, vessel departure and booking cancellation SHALL be distinct typed event proposals tied to the exact shipment and source. After source verification, only the authorized Purchase/Stock/Logistics/Transaction business command may execute a permitted transition with its own prerequisites. A supplier statement "booking complete" is evidence of a supplier-reported milestone, not conclusive terminal gate-in, loaded-on-vessel or completed international delivery; parent PO/SO totals derive from verified partial execution.

Acceptance: AC-EXP-09-007 · Runtime: **NOT_RUN**

### BRS-EXP-09-R008 — Source-scoped status and human review observability
**DESIGN** · **BOTH** · **Owner:** native Documents, Export exception presentation, Odoo Activities

Original received, extraction proposed, exact link pending, fields verified/applied, rejected, and downstream action accepted/refused SHALL be distinguishable source-backed statuses where needed using existing Odoo tracking and activity patterns. Document completeness SHALL be evaluated for the applicable shipment/milestone, not globally for an entire SO or four-load supplier PO.

Acceptance: AC-EXP-09-008 · Runtime: **NOT_RUN**

## BRS-EXP-10 — Logistics/Linda handoff, schedule constraints and audience-safe packet issuance

### BRS-EXP-10-R001 — Current booking requirements are revision-bound Logistics input
**LOCKED** · **P1** · **Owner:** Export current booking view; Logistics decision/dispatch owner

Export SHALL provide the exact current ocean booking, source revision, terminal/rail destination, ERD, cutoff, equipment requested and related shipment identities as read-only/typed input to Logistics. An ocean carrier reservation SHALL not be treated as the truck/drayage company commitment; Logistics owns drayage selection, accepted rate, work order and dispatcher state.

Acceptance: AC-EXP-10-001 · Runtime: **NOT_RUN**

### BRS-EXP-10-R002 — Independent supplier PO issue and later booking delivery
**LOCKED** · **P1** · **Owner:** native Purchase report + Export booking QWeb + Linda sending owner

A legitimate approved supplier PO SHALL be independently issuable through Linda's existing native-Purchase release without an ocean booking, buyer, load, or fictitious order. Supplier readiness and current booking confirmation MAY arrive later. Each current applicable booking original or clearly labeled booking summary SHALL be issued separately as its own revision-bound supplier communication when authorized. If both PO and booking are eligible simultaneously, a single message MAY carry two separately recognizable PDFs; they SHALL NOT be fused into a new document authority. Later weekly bookings under a still-open multi-load PO do not create, reapprove, or automatically reissue the commercial PO. A reference copy of unchanged PO is allowed only under explicit audience/revision-safe policy. Preserve distinct recipient, issue purpose, source revision, attempt and delivery evidence for PO issuance and booking issuance.

Acceptance: AC-EXP-10-002 · Runtime: **NOT_RUN**

### BRS-EXP-10-R003 — Carrier packet: booking and drayage Work Order, audience-safe
**LOCKED** · **P1** · **Owner:** Logistics QWeb and authorized Linda sender; Export booking PDF source

Export drayage dispatch SHALL use a movement-specific current audience-safe booking PDF and a distinct drayage Work Order PDF plus only operation-required carrier instructions. The Work Order SHALL contain booking reference, equipment/chassis configuration, origin, terminal/ramp destination, pickup windows, supplier hours, ERD, cutoff, appointment and authorized contact context, without supplier buy price, buyer sell price, margin or unnecessary buyer identity. Existing domestic three-PDF dispatch remains unchanged for domestic movements.

Acceptance: AC-EXP-10-003 · Runtime: **NOT_RUN**

### BRS-EXP-10-R004 — Material amendments protect pending commitments and mail
**DESIGN** · **P1** · **Owner:** Logistics/Linda transition and Odoo Mail, Export provides booking version

A changed booking, ERD, cutoff, terminal, actual equipment request or material delivery condition SHALL identify the exact affected Logistics movement and pending release/dispatch work orders, queue items and carrier commitments. The authorized Logistics/Linda owner SHALL invalidate or reassess only affected pending artifacts, retain prior sent evidence, and request new rate, schedule or acknowledgment if required. No automatic rebooking, PO reissuance or repeat send is authorized; unknown send outcome remains unknown.

Acceptance: AC-EXP-10-004 · Runtime: **NOT_RUN**

### BRS-EXP-10-R005 — ERD and cutoff are terminal constraints, not supplier pickup dates
**LOCKED** · **P1** · **Owner:** Export time values; Logistics pickup feasibility/appointments

For each specific load, Logistics SHALL plan a feasible supplier pickup and loaded gate-in from the current ERD, cutoff, terminal/ramp acceptance hours, appointments, loading duration, route transit, chassis/road constraints, buffer and authorized staging where used. ERD/cutoff SHALL NOT be converted directly into pickup appointments; inability to meet the window is a visible exception, not an invented ETA.

Acceptance: AC-EXP-10-005 · Runtime: **NOT_RUN**

### BRS-EXP-10-R006 — Equipment-aware freight context and explicit commitments
**DESIGN** · **P1** · **Owner:** Logistics freight context/booking owner

The equipment type, count, container/chassis constraints and requested movement intent SHALL be available to Logistics carrier/rate eligibility at the proper source. Freight reuse or rate confirmation SHALL not treat `equipment_class=None` as proof that a 40HC and a 20STD are equivalent. Binding to PO/owned material with no sale shall preserve company identity and approved authority independently of `sale_order_id`.

Acceptance: AC-EXP-10-006 · Runtime: **NOT_RUN**

### BRS-EXP-10-R007 — Terminal and voyage milestones have distinct evidence
**LOCKED** · **BOTH** · **Owner:** Logistics delivery tracking + native Documents proof; Export display

Pickup, arrival at terminal, accepted gate-in/rail receipt, booking compliance, vessel load/sail, destination discharge, actual customer delivery and legal title/risk milestones SHALL remain distinct facts. Carrier-issued originals, terminal receipts and actor verification govern proof; no status is inferred solely from planned cutoff, a driver photo, a shipping booking or a scanned package.

Acceptance: AC-EXP-10-007 · Runtime: **NOT_RUN**

### BRS-EXP-10-R008 — Movement authorization not tied to buyer visibility
**DESIGN** · **P1** · **Owner:** Logistics/Linda audience and buyer-optional movement policy

Carrier dispatch SHALL be authorized against exact company, physical load, approved purchase/stock and/or commercial order source, destination, booking when applicable, carrier acceptance, and movement-specific guards. An actual buyer MAY be present but is not necessary for every valid supplier-backed movement; if present, buyer identity remains shielded unless needed and authorized. Existing sales-specific buyer requirements SHALL remain in their legitimate sales workflow.

Acceptance: AC-EXP-10-008 · Runtime: **NOT_RUN**

## BRS-EXP-11 — Real-world booking correspondence, rolls and AI coordinator behavior

### BRS-EXP-11-R001 — Interpret the whole business correspondence package
**LOCKED** · **BOTH** · **Owner:** Native Mail/Documents intake; AI extraction

Ingest the original email thread, individual messages, attachments, sender/recipient roles, time and quoted/forwarded context as separate attributed evidence without conflating message authors or treating quoted history as the latest instruction. Extract typed candidates from email body, PDF, XLSX and available source-linked photo evidence where accessible, with provenance for each value.

Acceptance: AC-EXP-11-001 · Runtime: **NOT_RUN**

### BRS-EXP-11-R002 — Recognize document and message function, not just keywords
**LOCKED** · **BOTH** · **Owner:** Native Documents classification; plasticos_documents verification

Classify supplier PO, supplier readiness response, ocean booking original, booking summary, amendment/roll notice, cancellation, shipping/loading statement, scale ticket, load spreadsheet, gate receipt and externally hosted picture link as distinct evidence types. Do not label an operator-generated booking summary as a carrier-issued original or assume a link equals received pictures.

Acceptance: AC-EXP-11-002 · Runtime: **NOT_RUN**

### BRS-EXP-11-R003 — Resolve booking-versus-PO-versus-physical load identities
**LOCKED** · **BOTH** · **Owner:** plasticos_documents exact association; Export booking context

The matcher SHALL distinguish commercial PO 64014 from ocean booking 6509024800, link one PO to multiple separately executed bookings and one booking to its nominated count of containers, and link the actual physical container using corroborated container ID, ticket, seal and load index. It must not assume a single booking, PO, load, container, or supplier email are the same entity; ambiguous parent/child links require review.

Acceptance: AC-EXP-11-003 · Runtime: **NOT_RUN**

### BRS-EXP-11-R004 — Extract original booking attributes and missing-field truth
**LOCKED** · **P1** · **Owner:** Native AI extraction; Export target schema

From a source booking confirmation, extract exact booking string, steamship line, vessel, voyage, equipment class/count, ERD, cargo cutoff with supplied time precision, empty pickup site, loaded return site, receipt/port evidence, freight or material weight restrictions and other fields explicitly supplied. For POL and POD, keep unknown unless an authoritative source explicitly identifies the maritime ports; do not silently substitute local terminal or place of receipt.

Acceptance: AC-EXP-11-004 · Runtime: **NOT_RUN**

### BRS-EXP-11-R005 — Capture roll reasons, classifications, capacity and continuity
**LOCKED** · **BOTH** · **Owner:** Export booking history and supplier/carrier evidence

A notice of a rolled or revised booking SHALL retain source attribution, stated reason (distinct from inferred possibilities: supplier not ready, impossible freight, steamship-line cancellation, schedule/equipment change, unknown), affected booking/units, previous and candidate equipment quantities, vessel/voyage, cargo/document/VGM cutoff, terminal-specific ERD, ETD/ETA and relevant time zones. Where the booking number persists, treat multiple original files as version candidates and preserve each exact original and evidence timestamp. A later PDF, filename suffix or forwarded message does not independently prove the official chronology or replace another terminal's ERD. Distinguish same-booking revision, supplemental capacity, replacement booking and unresolved contradiction before emitting approved current fields to Logistics or externally issued documents.

Acceptance: AC-EXP-11-005 · Runtime: **NOT_RUN**

### BRS-EXP-11-R006 — Maintain field-level current value, version, and approval
**LOCKED** · **BOTH** · **Owner:** Export booking context; Documents verification

Each material field SHALL retain original raw value, parsed normalized value, source file/message locator, event time, supplier/carrier identity, assertion type, review status, effective time and superseded predecessor. A revised PDF using the same filename is distinct if content differs. An AI candidate becomes current only via an authorized deterministic policy: safe unambiguous initial fields may auto-apply when verified by controls, while conflicts, late changes and material dispatch-impacting values require review.

Acceptance: AC-EXP-11-006 · Runtime: **NOT_RUN**

### BRS-EXP-11-R007 — Use PO-level terms as constraints without copying financial values
**LOCKED** · **P1** · **Owner:** Native Purchase, Documents evidence; Export/Logistics read

Extract and link PO-level quantity, material grade, unit, agreed trade label, delivery responsibility, minimum weight, conditional loading requirements, pictures, prohibited contamination and tare instructions as source-backed constraints. These remain authoritative native PO/contract business facts; Export displays applicability per shipping unit and may detect conflicts but SHALL NOT rewrite PO rate, quantity, pricing, AP/AR or transaction terms.

Acceptance: AC-EXP-11-007 · Runtime: **NOT_RUN**

### BRS-EXP-11-R008 — Cross-check physical documents, not guessed shipping completion
**LOCKED** · **P1** · **Owner:** plasticos_documents evidence; native Stock/Logistics movement owners

Reconcile shipper completion email, loading spreadsheet and signed scale ticket on exact PO, booking, load index, date, container, seal, pieces, gross/tare/net and document identities. Physical weights and counts are evidence candidates, not necessarily invoice weight or legal verified gross mass. If reported identifiers/quantities conflict, preserve all versions, produce an exception and forbid unauthorized state advancement.

Acceptance: AC-EXP-11-008 · Runtime: **NOT_RUN**

### BRS-EXP-11-R009 — Track externally hosted photos and document completeness honestly
**LOCKED** · **P1** · **Owner:** Native Documents original/linked assets; plasticos_documents requirement verdict

Capture applicable loading-picture checklist from PO/booking, identify original pictures and external-link references, and show available, missing, inaccessible and verified status separately. Requirements may differ by PO and booking revision; no blanket global photo checklist, storage clone or fabricated proof. Native Documents stores originals or the authorized reference and PlasticOS Documents computes verification.

Acceptance: AC-EXP-11-009 · Runtime: **NOT_RUN**

### BRS-EXP-11-R010 — Guard shipment state changes and order balances
**LOCKED** · **BOTH** · **Owner:** Native Purchase/Sale/Stock and Logistics/Transaction guarded commands

Extraction SHALL produce typed event proposals; only the owning business command may advance supplier ready, loaded, pickup, gate accepted, sailed, inventory receipt/delivery or commercial state after all movement-specific checks and idempotency. One approved 40200-lb physical shipment does not complete a 200000-lb/five-container supplier PO, other bookings, or a customer multi-load SO. No direct AI writes to transaction.state or load.state.

Acceptance: AC-EXP-11-010 · Runtime: **NOT_RUN**

### BRS-EXP-11-R011 — Propagate only a verified material change to the right consumers
**DESIGN** · **BOTH** · **Owner:** Export publishes revisions; Logistics/Linda owns schedule/mail

When a verified current booking revision changes ERD, cutoff, vessel/voyage, terminal or requested equipment, Export SHALL publish the scoped booking-version delta. Logistics evaluates only impacted physical loads and pending commitments, holds/revalidates stale work orders and exact queued communications, while Linda retains sent and unknown send outcomes. Supplier PO and other sibling bookings remain intact; no automatic carrier booking/rebooking or sending outside authorized Logistics policies.

Acceptance: AC-EXP-11-011 · Runtime: **NOT_RUN**

### BRS-EXP-11-R012 — Offer a coordinator-style exception and audit view
**DESIGN** · **BOTH** · **Owner:** Export sourced view + native Activity; Documents and Logistics originals

The operator SHALL be able to see which email/PDF/XLSX supplied each field, what changed since the prior booking, who asserted it, whether source is carrier-issued or supplier-reported, confidence and verification status, affected load(s), time-window feasibility, outstanding shipping photos/documents, and the next permitted owner action. Do not create a second case-management system or hidden auto-acceptance.

Acceptance: AC-EXP-11-012 · Runtime: **NOT_RUN**

## BRS-EXP-12 — Phase 2 provider integrations (FindTEU + ACE AESDirect)

### BRS-EXP-12-R001 — FindTEU Phase 2 tracking adapter
**LOCKED** · **P2** · **Owner:** plasticos_export integration boundary; provider is external evidence producer

Phase 2 SHALL include a separately configurable FindTEU adapter for available ocean container tracking and ETA/terminal milestones, using its documented API and authorized account. It SHALL be optional for operation of the core ERP and Phase 1, and SHALL not book carriers, set rates, dispatch drayage, perform stock movements or create a competing shipment registry.

Acceptance: AC-EXP-12-001 · Runtime: **NOT_RUN**

### BRS-EXP-12-R002 — Exact container identity and optional booking-number tracking
**DESIGN** · **P2** · **Owner:** plasticos_export typed mapping; native Odoo shipping identity remains canonical

The FindTEU adapter SHALL bind a company-scoped provider observation to the exact known container and applicable ocean booking, with carrier/SCAC when known, including bookings with many containers. Booking-level tracking SHALL never assign a provider event to every container merely because they share an ocean reservation. Unknown, reused or conflicting identifiers require review.

Acceptance: AC-EXP-12-002 · Runtime: **NOT_RUN**

### BRS-EXP-12-R003 — Carrier observation is not commercial or stock authority
**DESIGN** · **P2** · **Owner:** plasticos_export evidence projection with Logistics/Stock/Docs retained

FindTEU events SHALL preserve observed-at, effective event time, provider, raw payload reference, carrier, location, actual-vs-estimated designation, and normalized milestone; source timestamps and provider certainty shall remain visible. ETA, ETD, gate-in, vessel-loaded, discharge and provider completed flags SHALL NOT by themselves close a sale, prove title change, post invoices, verify documents or bypass guarded Logistics/Stock transitions.

Acceptance: AC-EXP-12-003 · Runtime: **NOT_RUN**

### BRS-EXP-12-R004 — Rolls, replay, reversals and provider discrepancies
**DESIGN** · **P2** · **Owner:** plasticos_export booking reconciliation; Logistics authorizes affected actions

FindTEU ingestion SHALL be replay-safe and idempotent, preserve previous observations, distinguish later ETA estimates from actual voyage or terminal changes, and flag contradictions with the current verified booking/terminal documentary source. A roll or cancellation SHALL require attributable authoritative booking evidence and affected-container review. Provider errors, stale updates and absent coverage SHALL appear as unknown/exception, not silently overwrite current booking terms.

Acceptance: AC-EXP-12-004 · Runtime: **NOT_RUN**

### BRS-EXP-12-R005 — FindTEU tenancy, credentials, outages and coverage gate
**DESIGN** · **P2** · **Owner:** platform integration/security owner; Export is a consumer

FindTEU integration SHALL use tenant-isolated authorization and protected API keys, authenticated webhook ingress using a validated provider-supported verification design, quotas, bounded retries and error classification; protect commercial identity in outbound requests. It SHALL be feature-gated until provider contractual access, supported-carrier coverage, webhook security and a real-booking read-only proof pass. It SHALL not fabricate tracking status when provider data is missing.

Acceptance: AC-EXP-12-005 · Runtime: **NOT_RUN**

### BRS-EXP-12-R006 — AESDirect Phase 2 EEI filing support, not autonomous filing
**LOCKED** · **P2** · **Owner:** authorized USPPI/agent/filer and applicable regulator; Export filing context only

Phase 2 SHALL support ACE AESDirect EEI preparation, an applicability/exemption decision, the legally responsible USPPI or authorized agent, and status/evidence visibility. It SHALL NOT infer a mandatory EEI from an Incoterm or international booking alone, claim a regulatory determination absent the required facts, file EEI without an authorized filer, or require an AES account for Phase 1 or shipments outside applicable requirements.

Acceptance: AC-EXP-12-006 · Runtime: **NOT_RUN**

### BRS-EXP-12-R007 — Validate and assemble filing data from existing business sources
**DESIGN** · **P2** · **Owner:** native Odoo Sale/Purchase/Stock and authorized compliance reviewer; Export orchestration

The AESDirect filing preparation view SHALL source reportable commodity classification, destination, value, quantities, UOM, dates, parties, port, transport and shipment identifiers from their correct native owner and explicit reviewed inputs. Missing or uncertain EEI elements SHALL remain incomplete and be surfaced before handoff; AI extraction may propose facts but must not silently supply legal classification, reporting party, value, license or exemption determinations.

Acceptance: AC-EXP-12-007 · Runtime: **NOT_RUN**

### BRS-EXP-12-R008 — Official AESDirect portal, WebLink or supported bulk handoff
**DESIGN** · **P2** · **Owner:** authorized filer; connector only prepares supported handoff

Initial Phase 2 integration SHALL provide an authorized-user filing handoff to ACE AESDirect with a reviewable data packet and, where tested and approved, its documented WebLink Submission API for prepopulating the portal or a validated AESTIR/X12 bulk-upload file. AES WebLink still requires the filer to sign in, complete missing elements and submit in the official system. This requirement does NOT authorize an uncertified direct AES transmission service or unattended government filing.

Acceptance: AC-EXP-12-008 · Runtime: **NOT_RUN**

### BRS-EXP-12-R009 — Official response, ITN or exemption evidence and errors
**DESIGN** · **P2** · **Owner:** authorized filing authority + native Documents/PlasticOS verification

Only the official AES acceptance response and Internal Transaction Number (ITN), or applicable legally supported exemption evidence, SHALL support the corresponding filing outcome. Record filer, authoritative source, acceptance/rejection status, timestamp, exact shipment/export record and document original; reject ambiguous source matches and preserve rejected messages. Export SHALL display the verified projection and Logistics/other owners may consume it only according to their own lawful guarded workflow.

Acceptance: AC-EXP-12-009 · Runtime: **NOT_RUN**

### BRS-EXP-12-R010 — Amendments, cancellations, access control and certification boundary
**DESIGN** · **P2** · **Owner:** authorized filer and platform security; Export only coordinates evidence

Phase 2 filing corrections, voids, late amendments, role authorization and disclosures SHALL follow applicable official filing rules through the authorized filer. Keep the original filing decision, revised data, ITN/rejection evidence and source-linked audit trail. Optional certified direct transmission is DEFERRED as a separate future authorization/certification decision, not included in this Phase 2 scope. Failure or missing permissions SHALL fail closed without changing native order/invoice or stock state.

Acceptance: AC-EXP-12-010 · Runtime: **NOT_RUN**

## BRS-EXP-13 — Booking form, extended fields and documentary reconciliation

### BRS-EXP-13-R001 — Primary booking identity and existing six critical fields
**LOCKED** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The Export form SHALL present an authoritative booking identity with booking number, shipping line, POL, POD, cargo cutoff, ERD, plus source document, revision, effective date and exact company scope. No field SHALL be duplicated when its canonical Odoo equivalent already exists.

Acceptance: AC-EXP-13-001 · Runtime: **NOT_RUN**

### BRS-EXP-13-R002 — Additional independent deadline types and timezone
**LOCKED** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Booking form SHALL distinguish cargo/gate cutoff, documentation cutoff, VGM cutoff, and earliest loaded return; each holds date, time, time zone where known, source/version, and confirmed-versus-proposed status. Missing values remain unset rather than borrowed from another deadline.

Acceptance: AC-EXP-13-002 · Runtime: **NOT_RUN**

### BRS-EXP-13-R003 — Carrier, forwarder, vessel, voyage and transport milestones
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Export SHALL display shipping line, forwarder/booking agent where applicable, vessel, voyage, estimated/actual ETD and ETA with exact source. Recurring updates SHALL preserve old revisions. Physical arrival or gate-in belongs to Logistics/Stock evidence and is never inferred solely from ETA.

Acceptance: AC-EXP-13-003 · Runtime: **NOT_RUN**

### BRS-EXP-13-R004 — Port versus receipt, delivery and terminal locations
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Export SHALL distinguish POL, POD, place of receipt, final place of delivery, empty container pickup facility, loaded container return terminal and rail ramp. Export publishes applicable booking constraints; Logistics owns actual pickup, terminal appointments and execution.

Acceptance: AC-EXP-13-004 · Runtime: **NOT_RUN**

### BRS-EXP-13-R005 — Equipment quantity and multiple independent container identities
**LOCKED** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Export SHALL show requested equipment type and quantity at booking level and actual container number, seal, physical load, supplier PO, transaction and observed weights at container level. One ocean booking may include multiple supplier POs, multiple trade transactions and containers; allocation is exact and reversible.

Acceptance: AC-EXP-13-005 · Runtime: **NOT_RUN**

### BRS-EXP-13-R006 — Contract references and cargo constraints
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The booking form SHALL expose reference numbers (order, house/master bill where supported), booking date, booking contact, cargo description, classification code when evidenced, and contractual minimum/maximum cargo weights; use native product/partner/quantity models as canonical owners. Weight constraints never authoritatively rewrite actual or invoiced weight.

Acceptance: AC-EXP-13-006 · Runtime: **NOT_RUN**

### BRS-EXP-13-R007 — Optional commercial group and current booking status
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Booking date, contact, optional group, forwarder, agreement/reference and booking confirmation status SHALL be displayed when source-backed. Status must distinguish requested, confirmed, revised, rolled, cancelled, expired and partially fulfilled where those semantics are evidenced; do not infer confirmation from UI display or email timestamp.

Acceptance: AC-EXP-13-007 · Runtime: **NOT_RUN**

### BRS-EXP-13-R008 — AI extraction fills only exact authoritative targets
**DESIGN** · **BOTH** · **Owner:** plasticos_documents + native Odoo AI/Document owners; Export consumes validated candidates

Native Odoo 19 AI Documents may extract booking-form fields from emails, PDFs, and spreadsheets with page/message/field provenance. Existing `plasticos_documents` resolves exact booking, company, PO, transaction, container and revision before an authorized export action writes permitted fields. Ambiguous or material conflicts require review; AI must not set physical, commercial or financial states directly.

Acceptance: AC-EXP-13-008 · Runtime: **NOT_RUN**

### BRS-EXP-13-R009 — Native-first ergonomic booking form and tabs
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Booking presentation SHALL use Odoo form, smart buttons/related records and standard tabbed views for Shipments, Order Allocation, Instructions, Budget Expenses and Documentation only where there is an existing authoritative source; tabs must not host duplicate ledger, document, logistics or accounting data.

Acceptance: AC-EXP-13-009 · Runtime: **NOT_RUN**

### BRS-EXP-13-R010 — Carrier document and operator-generated booking distinction
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Export SHALL distinguish a carrier/forwarder original booking confirmation from an export-generated booking report/supplier summary. Files belong to native Documents, verification to PlasticOS Documents and communications to Linda; the form may expose print/send actions only through these owners.

Acceptance: AC-EXP-13-010 · Runtime: **NOT_RUN**

## BRS-EXP-14 — Native Odoo reporting and operational intelligence views

### BRS-EXP-14-R001 — Native Odoo reporting foundation only
**LOCKED** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The Export reporting component SHALL be built from Odoo 19 native list, search, favorite, group-by, pivot/graph, spreadsheet/export and QWeb report capabilities. Add only needed read-only joins/projections and views. No competing report engine, independent analytics store or user-specific report code copies.

Acceptance: AC-EXP-14-001 · Runtime: **NOT_RUN**

### BRS-EXP-14-R002 — Container-grain master report
**LOCKED** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The canonical detailed container report SHALL yield one row per physical container/journey allocation, sourced from exact native records: container, seal, booking, supplier PO, buyer SO where assigned, original physical load, commodity, weight, carrier, vessel, voyage, origin/destination and evidence status. Multi-party bookings and missing buyers are supported without dummy identities.

Acceptance: AC-EXP-14-002 · Runtime: **NOT_RUN**

### BRS-EXP-14-R003 — Booking-grain summary with drill-down
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The booking report SHALL show carrier, POL/POD, latest sourced deadlines and their time zones, equipment planned/assigned, vessel/voyage, ETD/ETA, number and summed weight of distinct containers, document completeness and exceptions. Booking summary and per-container report SHALL be separate grains with click-through to exact individual orders/loads.

Acceptance: AC-EXP-14-003 · Runtime: **NOT_RUN**

### BRS-EXP-14-R004 — Search, filters and stable saved views
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Provide search by Booking No., Container No., Seal, PO, SO, Source Worksheet/Trade identity, invoice/BOL where authorized, and filters for POL, POD, carrier, vessel, supplier, customer, grade, departments, ownership, status, deadlines and missing documents. Support saved Favorites and sharable role-scoped views via native Odoo.

Acceptance: AC-EXP-14-004 · Runtime: **NOT_RUN**

### BRS-EXP-14-R005 — Convenient interactive list and export
**LOCKED** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The list SHALL support default useful columns, optional column visibility, sort, group, page, drill-through and export of user-selected filtered rows to native XLSX/CSV according to permissions. No forced PDF for operational spreadsheets; print-ready layout SHALL use QWeb when needed.

Acceptance: AC-EXP-14-005 · Runtime: **NOT_RUN**

### BRS-EXP-14-R006 — Report column provenance and business-owner mapping
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The report schema SHALL explicitly map each required source column to an authoritative existing Odoo or PlasticOS owner. Missing sources SHALL appear as NOT_IMPLEMENTED/UNVERIFIED rather than fabricate a value; legacy labels are mapping hints, not permission for new duplicate fields.

Acceptance: AC-EXP-14-006 · Runtime: **NOT_RUN**

### BRS-EXP-14-R007 — Date semantics, time zones and cutoff risk
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Reporting SHALL preserve document cutoff, VGM cutoff, gate cutoff, ERD, actual supplier shipping date, estimated/actual sailing and arrival separately, including time zone and source/revision. Show missed or approaching deadlines from current authoritative facts without rescheduling loads directly.

Acceptance: AC-EXP-14-007 · Runtime: **NOT_RUN**

### BRS-EXP-14-R008 — Weight, equipment tare, VGM and units
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The detailed report SHALL distinguish cargo net weight, supplier or scale weight provenance, number of units, equipment tare, and compliant VGM when actually verified; display lb and metric ton using a single explicit conversion policy. Preserve null and unknown rather than printing zero as fact. Do not make a raw gross/tare formula into certified VGM.

Acceptance: AC-EXP-14-008 · Runtime: **NOT_RUN**

### BRS-EXP-14-R009 — Native pivots and useful operating metrics
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Provide native Odoo pivot/graph/dashboard measures for count of distinct physical containers, cargo weight by supplier/buyer/grade/month/port/steamship line, booking capacity-versus-allocated, unfulfilled PO/SO quantities, exceptions and document completeness. Financial measures must come from approved native accounting/transaction economics with stated recognition/actual-cost policy.

Acceptance: AC-EXP-14-009 · Runtime: **NOT_RUN**

### BRS-EXP-14-R010 — Audience-safe QWeb and source-linked revisions
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

Reports SHALL support separate print-ready booking summary, shipment/packing list when supported by verified physical facts, and operational exceptions/QWeb PDFs. Report generation records the source revision/as-of time; actual external sending remains Linda and original retention remains Documents. Supplier/trucker/buyer/internal audiences SHALL have distinct permitted fields.

Acceptance: AC-EXP-14-010 · Runtime: **NOT_RUN**

### BRS-EXP-14-R011 — Source workbook as conformance fixture, not production authority
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

The attached booking report.xlsx (372 data rows, 43 column headings) SHALL serve as a private comparison fixture to design semantics and test exports. Historical legacy report values do not become a new system of record; migrated values require validated exact identity and allowed ownership.

Acceptance: AC-EXP-14-011 · Runtime: **NOT_RUN**

### BRS-EXP-14-R012 — Access control and reproducible report scope
**DESIGN** · **BOTH** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

All reporting respects native company/tenant access, row rules, commercial confidentiality and customer/supplier/carrier audiences. Saved filters, download scope, calculated quantities, source timestamp and report user are reproducible. Use authorized Odoo actions; no raw unrestricted SQL reporting endpoint.

Acceptance: AC-EXP-14-012 · Runtime: **NOT_RUN**

### BRS-EXP-14-R013 — Phase 2 provider evidence is additive
**DESIGN** · **P2** · **Owner:** plasticos_export; native Odoo owns shared commercial and logistics facts

In Phase 2, optional FindTEU observations and AESDirect filing evidence may appear as separately labeled status columns and filters. Missing integration, a late provider update or unverified filing response shall never suppress a core report or rewrite native shipment/filing authority.

Acceptance: AC-EXP-14-013 · Runtime: **NOT_RUN**

### BRS-EXP-14-R014 — Booking capacity is equipment-specific and source-confirmed
**DESIGN** · **P1** · **Owner:** plasticos_export (projection; source owners unchanged)

The booking availability workbench SHALL show, per current company-scoped carrier reservation AND equipment type, requested capacity, confirmed capacity, committed booking-slot allocations, executed/loaded containers, remaining assignable capacity and source validity. Confirmed capacity is not derived from a sales order or empty field. Only active source-confirmed capacity is eligible; cancelled, expired, proposed or rolled bookings are labelled separately. An operational hold, if genuinely authorized, is separately identified and reduces assignable capacity; a tentative candidate does not. A shipped container does not reopen a slot without explicit carrier evidence.

Acceptance: AC-EXP-14-014 · Runtime: **NOT_RUN**

### BRS-EXP-14-R015 — One booking slot can serve multiple correctly attributed cargo lines
**DESIGN** · **P1** · **Owner:** plasticos_export (projection; source owners unchanged)

Booking-space allocation SHALL identify an exact distinct equipment slot or legitimate planned shipment assignment, link it to eligible actual load/transaction or approved native order lines as applicable, and preserve zero or more related supplier PO and customer SO lines without multiplying the slot. The physical ISO container number may be unknown at planning time; later evidence binds the real number to the same slot. Export owns booking-slot assignment only, never commercial ordered/reserved/delivered quantity or actual stock movement. No fictitious load is created for a tentative allocation.

Acceptance: AC-EXP-14-015 · Runtime: **NOT_RUN**

### BRS-EXP-14-R016 — Explicit allocation commands respect capacity and revision
**DESIGN** · **P1** · **Owner:** plasticos_export (projection; source owners unchanged)

Assign, release, substitute, split or reallocate booking space SHALL be an authorized explicit booking operation with company, equipment, responsible source, target slot or movement, revision and audit trail. Concurrent assignments must not overcommit capacity. If a booking revision lowers quantity below committed slots or changes equipment, show the impacted allocations and block unsafe new commitment; never silently delete an actual container, undo physical delivery, rebook trucks, reissue communications or pretend a released slot exists without evidence.

Acceptance: AC-EXP-14-016 · Runtime: **NOT_RUN**

### BRS-EXP-14-R017 — Native-first Bookings control center with actionable drilldowns
**DESIGN** · **P1** · **Owner:** plasticos_export

The Export Overview SHALL be the native Odoo landing dashboard and summary/navigation surface for **all six Phase 1 core reports** named in BRS-EXP-14-R021: Booking Space Availability; Booking Allocation / Container Manifest; Open PO / SO Fulfillment; Container Shipment Register; Cutoff & Booking Exceptions; and Missing Export Documents. It SHALL present at least one genuinely informative source-owned, grain-correct current metric, exception or compact visualization per report, with a clearly identifiable direct link to that exact report. Each card/chart/table element SHALL drill to the contributing filtered records under the user’s company/role access, with per-metric source and as-of information and a path from report to exact booking, slot, container, commercial order or document evidence. Summary is not a replacement for the six reports. Prefer native Odoo Spreadsheet Dashboard, list/pivot/graph and native actions, with a searchable-list fallback if the Dashboard app is unavailable. No separate reporting engine or new writer.

Acceptance: AC-EXP-14-017 · Runtime: **NOT_RUN**

### BRS-EXP-14-R018 — Available bookings and unbooked demand remain distinct
**DESIGN** · **P1** · **Owner:** plasticos_export (projection; source owners unchanged)

Provide saved native lists for Available Bookings, Fully Allocated, Awaiting Carrier Confirmation, Rolled/Cancelled, Unallocated Eligible Cargo, Ready without Booking, Buyer Unassigned, and Booking with Multiple Suppliers. Availability is carrier capacity; unallocated demand is a distinct eligible physical/commercial need. Bookings with no current PO/load remain visible. Buyer-unassigned cargo must remain visible rather than being rejected or silently assigned to an arbitrary SO.

Acceptance: AC-EXP-14-018 · Runtime: **NOT_RUN**

### BRS-EXP-14-R019 — Deadline and allocation risk view without second dispatch authority
**DESIGN** · **P1** · **Owner:** plasticos_export (projection; source owners unchanged)

Provide a booking-focused calendar and saved views for ERD, cargo cutoff, documentation cutoff, VGM cutoff, ETD/ETA, impending release and amendments, preserving source revision/time zone. Show whether allocations and supplier readiness permit a feasible move based on Logistics owner facts. Export SHALL NOT reschedule, select carriers, send messages, or declare gate-in; user actions route to the authoritative Logistics/Linda commands or native Activities.

Acceptance: AC-EXP-14-019 · Runtime: **NOT_RUN**

### BRS-EXP-14-R020 — Per-booking document readiness is read-only and attributable
**DESIGN** · **P1** · **Owner:** plasticos_export (projection; source owners unchanged)

The booking and container workspaces SHALL display only operation-specific document requirements, verified/current evidence, missing items, superseded source revisions, supplier loading photos and actual proof of terminal acceptance from the Documents/Logistics authorities. A source booking notice and generated booking summary must be visibly distinguished. Native Activities present internal exceptions; Linda owns any external chase or outbound send.

Acceptance: AC-EXP-14-020 · Runtime: **NOT_RUN**

### BRS-EXP-14-R021 — Minimal report suite with explicit grain and replayable filters
**DESIGN** · **P1** · **Owner:** plasticos_export

The six required Phase 1 reports SHALL be (1) Booking Space Availability, (2) Booking Allocation / Container Manifest, (3) Open Supplier PO / Customer SO Fulfillment, (4) Container Shipment Register, (5) Cutoff & Booking Exceptions, and (6) Missing Export Documents. Each SHALL have a stable Odoo list/pivot/graph/spreadsheet route and grain-correct report scope so the Overview can summarize and open the exact contributing rows. Export Economics is an optional separate authorized report when Accounting provides accepted figures; it is not the sixth mandatory report. QWeb is for audience-safe printable booking/packing/exception snapshots. Counts use booking-slot, container-journey, order-line, amendment or evidence-obligation grains as appropriate, with source-authenticated units, weights, company permissions, revision and as-of. No duplicate report ledger, second scheduler or mailer.

Acceptance: AC-EXP-14-021 · Runtime: **NOT_RUN**

### BRS-EXP-14-R022 — Six-report dashboard coverage and exact filter-preserving navigation
**DESIGN** · **P1** · **Owner:** plasticos_export

Each of the six Phase 1 dashboard sections SHALL bind to the same authoritative, appropriately filtered source population as its linked report. The required dashboard-to-report contract is: availability -> current confirmed/allocated/free slots by equipment; allocations -> committed slots and overallocations; fulfillment -> outstanding PO/SO line quantity and ready-but-unbooked demand with units; shipment register -> distinct loaded/in-transit/terminal-accepted containers; deadline exceptions -> imminent cutoffs, rolls and stale booking revisions; missing documents -> exact overdue or missing current verified evidence obligations by owner. Clicking a tile/measure SHALL open its matching report with compatible company, operator rights, period, equipment, booking, state, source-revision and exception filters; report rows SHALL then open the correctly authorized underlying business record/evidence. If native Odoo action/filter propagation cannot preserve a chosen cross-source scope, provide the minimum authorized action binding, never a custom dashboard engine. Label when-as-of, stale/pending/unknown, report currentness and privilege-limited omissions. Empty or inaccessible populations SHALL not masquerade as an accepted zero.

Acceptance: AC-EXP-14-022 · Runtime: **NOT_RUN**
