# BRS-EXP-09: Native Odoo 19 AI booking extraction, exact association and guarded transitions

**Classification:** Operator-confirmed business scenarios (LOCKED); technical source placement and guarded interfaces (DESIGN).
**Primary owner:** Documents AI intake; PlasticOS Documents evidence; Export booking owner; native state owners.
**Scope:** Phase 1 supports multiple partial loads/bookings and legitimate buyer-optional stock; Phase 2 extends the same identities for resale on the water.
**Non-ownership:** No second Odoo Stock, Purchase, Sale, Mail, Documents verifier, freight or transaction state engine.
**Acceptance:** All cases NOT_RUN, pending independent Enterprise/runtime proof.

## Rules

### BRS-EXP-09-R001: Use Odoo native AI Documents before custom extraction

**LOCKED · BOTH · owner: `native Odoo Documents AI, installed capability verified`.** When the approved Odoo 19 Enterprise AI Documents capability is available, incoming booking confirmations and amendments SHALL be classified and candidate booking data extracted through that native facility, not a parallel Export OCR/doc ingestion engine. Actual installed APIs, AI licensing/permissions, coverage and fallback SHALL be verified before activation; if unavailable, permit controlled manual booking entry.

- **Positive:** A carrier booking PDF enters native Documents and yields editable candidate data with the original retained.
- **Negative:** Export introduces a second file storage/OCR pipeline or claims unverified AI integration works in CE.
- **Related existing BRS:** Odoo 19 AI Document sort; BRS-POS-02; BRS-EXP-01-R005.
- **Acceptance:** `AC-EXP-09-001` / NOT_RUN.

### BRS-EXP-09-R002: Typed field extraction with source-level provenance

**LOCKED · BOTH · owner: `native AI candidate intake; export booking field owner`.** Native Odoo AI SHALL extract candidate values from both message body and attachments with explicit origin: purchase order reference, booking No., shipping line, POL/POD when present, ERD, terminal/cargo cutoff, equipment quantity/type, vessel/voyage, empty pickup and loaded return locations, dates, ticket, actual container/seal, reported weights and document requirements. Preserve exact strings including leading zeros, distinguishing time/date precision, reporter, field source and confidence. An absent field is UNKNOWN, never filled from a nearby attachment or assumption.

- **Positive:** PO 64014 and Booking 6509024800 are extracted from separate files, with 1 x 40HQ, 10/05 ERD and 10/09 16:00 cutoff traced to the dated booking PDF; missing POL/POD remain unknown rather than inferred from Long Beach terminal.
- **Negative:** AI mistakes order 64014 for ocean Booking No., infers POD from container destination, or converts date-only ERD into an exact midnight appointment.
- **Related existing BRS:** BRS-EXP-02-R002..R004; BRS-POS-03.
- **Acceptance:** `AC-EXP-09-002` / NOT_RUN.

### BRS-EXP-09-R003: Exact company-and-booking match, never latest partner

**LOCKED · BOTH · owner: `PlasticOS Documents exact link and Export booking lookup`.** Before assigning an extracted fact, resolve company, source thread, exact PO/order and applicable booking revision, shipment/load and actual physical container/ticket via corroborated typed identifiers. Multiple bookings may reference one PO; booking identity alone does not identify a physical load before container/ticket linkage. Party-only, latest-open transaction and PDF filename matches are not sufficient. A conflict or unresolved one-to-many case enters a review/exception queue without incorrect downstream writes.

- **Positive:** The scale ticket and spreadsheet both specify PO 64014, booking 6509024800, ticket 1728952 and container CSNU8490558, resolving that specific physical load without attaching four other future loads.
- **Negative:** An email from the same supplier links an amended booking to the most recent transaction or globally changes all five PO loads.
- **Related existing BRS:** Observed `plasticos_documents_native/models/document_native.py::_auto_link_partner`; BRS-POS-03-R002.
- **Acceptance:** `AC-EXP-09-003` / NOT_RUN.

### BRS-EXP-09-R004: Ambiguity, conflicting originals and correction review

**LOCKED · BOTH · owner: `Documents verification owner; authorized export booking reviewer`.** When several candidate bookings, loads, companies, amended notices, or inconsistent ERD/cutoff fields are possible, AI SHALL abstain from authoritative writes and create a reviewable exception with candidate IDs and conflicting originals. A verified, authorized actor SHALL resolve exact linkage or reject it; the superseded/original evidence remains accessible.

- **Positive:** Two similar bookings share a carrier and supplier; ambiguous PDF waits in an exact-match review queue without changing either shipment.
- **Negative:** AI guesses the most recent load or changes all four siblings on a single ambiguous booking email.
- **Related existing BRS:** BRS-EXP-06-R002; BRS-POS-03-R003,R006.
- **Acceptance:** `AC-EXP-09-004` / NOT_RUN.

### BRS-EXP-09-R005: Version-safe, idempotent apply

**DESIGN · BOTH · owner: `Export booking owner; native Documents original/version keeper`.** Native intake SHALL deduplicate identical original document bytes and email events while retaining distinct versions even when filenames repeat. AI SHALL classify a newly observed booking-related notice as initial confirmation, same-booking revision/roll, cancellation, replacement-booking cross-reference, or supplemental capacity only when evidence suffices; otherwise retain unresolved as a proposal. Prior originals and values remain queryable. A material booking change shall trigger only exact affected downstream reassessment, never automatic carrier rebooking, blanket load cancellation or commercial PO reissue.

- **Positive:** A later two-container ERD/cutoff email is held as a candidate revision of the earlier one-container booking until same-booking identity/authority is verified; a confirmed roll supersedes only the affected booking revision.
- **Negative:** AI assumes the latest email is an authoritative replacement despite missing booking number or overwrites a September original because the PDF has the same filename.
- **Related existing BRS:** BRS-EXP-02-R004; BRS-EXP-10-R004.
- **Acceptance:** `AC-EXP-09-005` / NOT_RUN.

### BRS-EXP-09-R006: Apply structured values only through approved owner interface

**DESIGN · BOTH · owner: `Export booking/record owner; Documents extraction producer`.** The AI component SHALL output an extraction proposal to a bounded write action that checks company, actor permission, field ownership, exact target, revision precondition and required evidence. Only fields owned by Export MAY be written there; original document classification/verification stays with Documents, transport facts with Logistics, contract values with Sales/Purchase, and stock with Inventory.

- **Positive:** Confirmed booking extraction updates the exact booking record and its linked view without mutating a purchase order or load freight rate.
- **Negative:** An AI server action directly writes arbitrary model/field values, bypasses access controls or sets Documents verified=true.
- **Related existing BRS:** Odoo 19 AI Server Actions documentation; BRS-EXP-01-R002.
- **Acceptance:** `AC-EXP-09-006` / NOT_RUN.

### BRS-EXP-09-R007: Transaction/load state changes only via validated commands

**LOCKED · BOTH · owner: `native state transition owner (Transaction/Logistics/Stock/Accounting)`.** Document-derived supplier readiness, loaded shipment confirmation, carrier acknowledgment, terminal/rail acceptance, vessel departure and booking cancellation SHALL be distinct typed event proposals tied to the exact shipment and source. After source verification, only the authorized Purchase/Stock/Logistics/Transaction business command may execute a permitted transition with its own prerequisites. A supplier statement "booking complete" is evidence of a supplier-reported milestone, not conclusive terminal gate-in, loaded-on-vessel or completed international delivery; parent PO/SO totals derive from verified partial execution.

- **Positive:** The Oct 8 supplier completion email and ticket 1728952 support a reviewable Load 1 shipped/loaded event; other four PO loads remain open and terminal gate-in remains unverified.
- **Negative:** AI marks the five-container PO fulfilled or load delivered-to-port/at sea solely on a supplier email saying booking complete.
- **Related existing BRS:** BRS-EXP-01-R004; BRS-EXP-06-R003; existing `plasticos.transaction.state`.
- **Acceptance:** `AC-EXP-09-007` / NOT_RUN.

### BRS-EXP-09-R008: Source-scoped status and human review observability

**DESIGN · BOTH · owner: `native Documents, Export exception presentation, Odoo Activities`.** Original received, extraction proposed, exact link pending, fields verified/applied, rejected, and downstream action accepted/refused SHALL be distinguishable source-backed statuses where needed using existing Odoo tracking and activity patterns. Document completeness SHALL be evaluated for the applicable shipment/milestone, not globally for an entire SO or four-load supplier PO.

- **Positive:** Week 1 has current verified gate proof and week 2 document is missing; only week 1 shows its milestone complete.
- **Negative:** A single Booking PDF marks every order line document-ready or suppresses unresolved extraction review.
- **Related existing BRS:** BRS-EXP-03-R002; BRS-EXP-08-R003,R004.
- **Acceptance:** `AC-EXP-09-008` / NOT_RUN.

