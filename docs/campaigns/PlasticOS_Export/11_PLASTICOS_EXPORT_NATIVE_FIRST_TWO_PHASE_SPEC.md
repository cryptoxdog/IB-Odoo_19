# `plasticos_export`: two-phase native-first product specification

**Status:** operator-locked *product intent*, unadmitted implementation specification. Explore/design only. The narrowest viable extension is **document coordination + native report templates + native views**, with a small export-booking field surface only where unowned by an existing model.

## 1. Two phases, one shared semantic identity

| Capability | Phase 1: current domestic-to-export-terminal/FAS operation | Phase 2: ocean-selling exporter extension |
|---|---|---|
| Actual user | U.S. recycling seller/trader arranging buyer pickup or paying inland freight to port/rail | Seller/shipper arranging international sale and freight |
| Trade usage | Operator `FOB` = buyer pickup; operator `FAS` = freight included to agreed port/rail | Operator `CNF/C&F` may denote freight-inclusive ocean sale; formal `CFR`, `CIF` etc only where contract specifies |
| Booking | Capture third-party/buyer/forwarder booking evidence and six fields | Also capture own booking/freight commitments and subsequent carrier amendments |
| Physical flow | Existing Odoo stock/package QR -> existing load -> yard/rail/terminal documentary proof | Reuse same stock, material, booking, container, seal identities; add forwarder/ocean milestones |
| Documents | Capture inbound booking/ERD/cutoff, carrier/terminal correspondence, receipts/tickets and loading proof; issue authorized current pickup/delivery and source-derived reports | Expand packet as actually needed: shipping instructions, commercial invoice, container packing list, VGM evidence, carrier-issued ocean B/L, export filings/authorizations, remittance/release proofs |
| Reports | Booking/dispatch sheet, exception and missing-document list, cargo/package manifest from existing records | Destination/forwarder document packet, outstanding approvals, export container status, document reconciliation |
| Views | Booking list/form, cutoff/ERD calendar and exceptions, linked documents and existing load links | Ocean shipment and document readiness by booking/container/buyer/destination |
| Explicit exclusion | No need to manage overseas destination milestones, ocean freight purchase, or foreign customs on the operator's behalf | No separate stock/finance/document/mail engine; no universally assumed regulatory filing capability |

### The commercial-vs-legal vocabulary rule

- **Industry term** = how the recycler quotes the deal, e.g. `FOB pickup` or `FAS delivered port/rail`.
- **Contractual trade rule** = separate, explicitly agreed formal Incoterm and named place, if present. ICC FOB/FAS definitions are *not* the shorthand above. For container gate-in/rail handoffs FCA may be relevant, but **do not infer, impose, silently convert, or change contract terms**.
- **Who arranges booking, who pays freight, delivery/handoff evidence, exporter/USPPI/filing roles, insurer, importer and buyer** = actual explicit party/contract facts, not deduced solely from either string. Formal CFR is not a license to treat risk as transferred at arrival.
- **Document recipient** = explicit approved audience; do not expose buyer/supplier commercially sensitive details across boundaries.

## 2. Minimum field surface and provenance

The six first-class fields stay exactly named as in v1.1: **Booking No., Steamship Line, Port of Loading, Port of Discharge, Cut Off, Earliest Return Date**. *Only add storage if existing native/PlasticOS fields cannot own a precise value*. Distinguish booking number, sale/purchase order, truck load, ocean container, seal, lot/package, and B/L references. Many ocean containers may share a booking. Prefer existing `res.partner` for shipping line, existing `account.incoterms` for formal Incoterms, existing Odoo purchase/sales/freight information, existing PlasticOS transaction line container/seal fields, Odoo stock package and delivery records. A thin export shipment/booking linkage record is **conditional**, not assumed.

Retain carrier or terminal source, receipt time, revision, timezone and time precision for ERD and cargo cutoff. **ERD** = earliest carrier/terminal acceptance for a *loaded* export container. **Cut Off** = specified terminal cargo gate-in deadline; independent SI, VGM, documents, customs, rail or other cutoffs must not be collapsed into it. Updates preserve prior values and what changed. A stale deadline remains evidence, not the current truth. For rail, record the actual specified terminal/event and do not assume the port rule transfers unchanged.

## 3. Documents first: one authority per fact

**Inbound:** existing Odoo Mail / authorized Documents alias -> native stored original and version -> exact company, source, document type, sender, sale/purchase, export booking, physical load and/or container association -> existing `plasticos_documents` typed evidence/compliance verification -> native Activity/exception where missing or ambiguous. The same original may support multiple records through typed links; it must not be copied to create multiple authoritative originals. If Enterprise Documents features are not proven installed/licensed, gate their usage and use permitted native attachment/mail facilities without creating an independent external file repository.

**Outbound:** authorized Odoo QWeb report and document revision -> explicit internal approval/business release -> existing `plasticos_logistics`/Linda outward-message owner with native Odoo Mail, threading and recipient-safe content -> actual send-state evidence. `plasticos_export` **must not** become a second sender/reminder scheduler. Carrier/terminal/buyer/forwarder documents must remain audience-specific. Use native `mail.activity`, `ir.cron` and `base.automation` only through the existing approved responsibility boundaries, with automation activation later.

**Phase 1 likely document kinds:** purchase/sales and rate confirmations where applicable; third-party booking confirmation; carrier/terminal published ERD and Cut Off; drayage dispatch instructions; gate appointment/rail instructions where applicable; container ID and seal evidence; scale/CST document; warehouse packing/loading evidence; gate-in/terminal interchange receipt; outbound origin-side document packet; carrier/forwarder correspondence; corrections and superseded versions. Not every shipment requires every type. Disposition comes from exact case/contract/role, not a universal hard-coded mandatory list.

**Phase 2 additional kinds as applicable:** shipping instructions; commercial invoice/packing list for foreign buyer; freight invoice; VGM submitted/accepted evidence; forwarder/carrier ocean B/L and telex/release status; export declaration/ITN or approved exception where required; regulated material/destination authorization; vessel/voyage and arrival milestones; buyer financial/release confirmation. The exporter/filing agent retains independent regulatory and document-issuance authority, and scanned packages do not prove compliance or VGM certification.

## 4. Reports and views, not a second application

**Candidate Phase 1 native UI:**
- a booking-linked list/form with six first-class fields, owner/next action and related SO/PO/load/stock picking;
- ERD/Cut Off calendar + urgent exceptions (timezone/provenance visible), view derived from current booking evidence;
- incoming/outgoing documents tab with Missing / Received / Verified / Superseded / Not applicable **as an existing authoritative evidence projection**, not a new independent compliance writer;
- lightweight source-derived *loading/booking/dispatch sheet* and document checklist, avoiding re-keyed product/weight/party details;
- existing Odoo QWeb reports/templates for outbound current audience-safe documents; cargo packing list derived from actual stock packages and real verified quantities.

**Candidate Phase 2 extensions:** shipment/document-readiness view; booking-to-container roll-ups, vessel/voyage/forwarder metadata, existing invoice/terms links; context-sensitive international PDF report variants; exception dashboard for export documents and schedules. Use Odoo list/form/kanban/calendar/pivot/report features as appropriate; no new dashboard framework, PDF renderer, general-purpose workflow engine or carrier aggregator without evidence.

## 5. Nonnegotiable domain boundaries

1. **One physical writer:** stock moves, package/lot identities and inventory remain in native Odoo Inventory. QR event alone is not authoritative delivery or terminal acceptance.
2. **One commercial writer:** native Sales/Purchase and approved Accounting actions own PO/SO, financial quantities, invoices, posting and settlement; scale/manifest/VGM observations are not automatic AP/AR overrides.
3. **One original file + one verification writer:** native Documents/attachments own file; existing `plasticos_documents` owns typed verified business evidence; upload or AI tag never equals legal approval or compliance.
4. **One external sender:** Linda/logistics through native Mail where it is the approved communication owner; no parallel cron, send queue, or duplicate customer/carrier outreach.
5. **Real handoff evidence:** booking receipt, pickup, loaded, terminal gate-in and vessel-on-board are different facts. Do not elevate an expected schedule, QR scan or uploaded ticket to a later event.
6. **Least privilege:** company record rules, authorized roles, source/recipient provenance, no external Documents portal/link unless the user separately changes the existing BRS.
7. **Separate obligation:** Phase 1 can still have actual export regulatory obligations. Who must file does not automatically follow from industry label `FAS`, `FOB`, or carrier booking party.
8. **Minimal model surface:** only a demonstrated missing export-specific coordination relation/field is eligible for new code. No duplicate logistics order, invoice, physical shipment record, file repository, general state machine, deadline scheduler or report engine.

## 6. BRS alignment: reference, never duplicate

Read alongside the attached `PlasticOS_Native_First_BRS_v1.0.0_2026-10-25` (**frozen working, not repository-admitted**). Especially: `BRS-POS-01-R001..R003` native-first/one owner; `BRS-POS-02-R001..R011` original Documents custody/intake/no external sharing; `BRS-POS-03-R001..R008` exact association/verification/no side-effects; `BRS-POS-05` native stock; `BRS-POS-06` native POs/SOs; `BRS-POS-09-R001..R006` native Activities/automation and one external reminder; `BRS-POS-10-R001..R016` Linda/outward logistics and native reports; `BRS-POS-11` security/recipient boundary; `BRS-POS-12` separate admission/execution.

The BRS is a later reference input, **not copied or imported as authority**. Any technical implementation must first resolve actual admitted Odoo repository ADR/BRS authority at its own target revision and settle any conflict before action.
