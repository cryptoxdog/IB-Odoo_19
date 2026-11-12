# BRS-EXP-11: Real-world booking correspondence, rolls and AI coordinator behavior

**Status:** Operator-confirmed business behavior LOCKED where indicated; implementation allocation subject to owners and native-first verification. **Not repository-admitted.**

**Goal:** Native Odoo Documents + AI transform mail/PDF/XLSX evidence into exact, versioned booking/load facts, without becoming an alternative Documents, Logistics, Stock or Accounting authority.

## Rules

### BRS-EXP-11-R001: Interpret the whole business correspondence package

**LOCKED · BOTH · owner: `Native Mail/Documents intake; AI extraction`.** Ingest the original email thread, individual messages, attachments, sender/recipient roles, time and quoted/forwarded context as separate attributed evidence without conflating message authors or treating quoted history as the latest instruction. Extract typed candidates from email body, PDF, XLSX and available source-linked photo evidence where accessible, with provenance for each value.

- **Positive:** PO issued Sep 4, separate booking forwarded Sep 30, supplier reported completion Oct 8, later Oct 20 instruction remain four separately timed claims, all linked but not flattened into a single current statement.
- **Negative:** The latest PDF filename or subject alone overwrites booking fields or an email quote is mistaken for a fresh carrier instruction.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-001` / NOT_RUN.

### BRS-EXP-11-R002: Recognize document and message function, not just keywords

**LOCKED · BOTH · owner: `Native Documents classification; plasticos_documents verification`.** Classify supplier PO, supplier readiness response, ocean booking original, booking summary, amendment/roll notice, cancellation, shipping/loading statement, scale ticket, load spreadsheet, gate receipt and externally hosted picture link as distinct evidence types. Do not label an operator-generated booking summary as a carrier-issued original or assume a link equals received pictures.

- **Positive:** AI recognizes 1728952 LOAD 1.pdf as a scale ticket and the supplier Oct 8 email as a completion assertion while the photograph link remains pending access/verification.
- **Negative:** The phrase Booking Confirmation in a subject causes proof-of-vessel-load or all required loading photos to be marked verified.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-002` / NOT_RUN.

### BRS-EXP-11-R003: Resolve booking-versus-PO-versus-physical load identities

**LOCKED · BOTH · owner: `plasticos_documents exact association; Export booking context`.** The matcher SHALL distinguish commercial PO 64014 from ocean booking 6509024800, link one PO to multiple separately executed bookings and one booking to its nominated count of containers, and link the actual physical container using corroborated container ID, ticket, seal and load index. It must not assume a single booking, PO, load, container, or supplier email are the same entity; ambiguous parent/child links require review.

- **Positive:** XLSX row binds booking 6509024800, PO 64014, container CSNU8490558, seal 7695652, ticket 1728952, Load 1 without consuming all five PO units.
- **Negative:** One 40HQ booking creates five loads or a generic vendor email attaches the ticket to an unrelated future booking.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-003` / NOT_RUN.

### BRS-EXP-11-R004: Extract original booking attributes and missing-field truth

**LOCKED · P1 · owner: `Native AI extraction; Export target schema`.** From a source booking confirmation, extract exact booking string, steamship line, vessel, voyage, equipment class/count, ERD, cargo cutoff with supplied time precision, empty pickup site, loaded return site, receipt/port evidence, freight or material weight restrictions and other fields explicitly supplied. For POL and POD, keep unknown unless an authoritative source explicitly identifies the maritime ports; do not silently substitute local terminal or place of receipt.

- **Positive:** Booking PDF yields COSCO Shipping Lines, 1 x 40HQ, vessel CMA CGM JEAN GABRIEL, voyage MTE0, ERD Oct 5 and cutoff Oct 9 16:00, but explicit POD stays unknown.
- **Negative:** The Long Beach empty pickup terminal is stored as Port of Discharge or the cutoff receives a fabricated time zone.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-004` / NOT_RUN.

### BRS-EXP-11-R005: Capture roll reasons, classifications, capacity and continuity

**LOCKED · BOTH · owner: `Export booking history and supplier/carrier evidence`.** A notice of a rolled or revised booking SHALL retain source attribution, stated reason (distinct from inferred possibilities: supplier not ready, impossible freight, steamship-line cancellation, schedule/equipment change, unknown), affected booking/units, previous and candidate equipment quantities, vessel/voyage, cargo/document/VGM cutoff, terminal-specific ERD, ETD/ETA and relevant time zones. Where the booking number persists, treat multiple original files as version candidates and preserve each exact original and evidence timestamp. A later PDF, filename suffix or forwarded message does not independently prove the official chronology or replace another terminal's ERD. Distinguish same-booking revision, supplemental capacity, replacement booking and unresolved contradiction before emitting approved current fields to Logistics or externally issued documents.

- **Positive:** The source PDFs with 3, 4 and 5 x 40HC under booking 6509024800, with a cutoff change from October 9 to October 12 and sailing change October 16 to 18, generate a sourced comparison and a separately reviewable terminal-ERD discrepancy; only accepted affected commitments are revalidated.
- **Negative:** PDF filename ordering alone is treated as official issue chronology, competing terminal ERDs are flattened into one, an unrelated load is rescheduled, or a 1-container supplier summary is overwritten by an unverified 5-container email.
- **Related existing BRS:** BRS-EXP-02/09/10/13; BRS-POS-02/03/10; POS-INV-06/16/21/22/23.
- **Acceptance:** `AC-EXP-11-005` / NOT_RUN.

### BRS-EXP-11-R006: Maintain field-level current value, version, and approval

**LOCKED · BOTH · owner: `Export booking context; Documents verification`.** Each material field SHALL retain original raw value, parsed normalized value, source file/message locator, event time, supplier/carrier identity, assertion type, review status, effective time and superseded predecessor. A revised PDF using the same filename is distinct if content differs. An AI candidate becomes current only via an authorized deterministic policy: safe unambiguous initial fields may auto-apply when verified by controls, while conflicts, late changes and material dispatch-impacting values require review.

- **Positive:** Oct 20 email offers 2 x 40HQ / Oct 26 ERD / Oct 30 cutoff as candidates; old 1 x 40HQ / Oct 5 / Oct 9 remain readable and operative until version/match authority is established.
- **Negative:** AI picks a new cutoff just because email timestamp is later or treats same filename as identical content.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-006` / NOT_RUN.

### BRS-EXP-11-R007: Use PO-level terms as constraints without copying financial values

**LOCKED · P1 · owner: `Native Purchase, Documents evidence; Export/Logistics read`.** Extract and link PO-level quantity, material grade, unit, agreed trade label, delivery responsibility, minimum weight, conditional loading requirements, pictures, prohibited contamination and tare instructions as source-backed constraints. These remain authoritative native PO/contract business facts; Export displays applicability per shipping unit and may detect conflicts but SHALL NOT rewrite PO rate, quantity, pricing, AP/AR or transaction terms.

- **Positive:** PO 64014 describes 200000 lb / 5 containers, FAS Port / Supplier Delivered, minimum 36000 lb per 40HQ and specified photo sequence, which are visible for each applicable load.
- **Negative:** The scale ticket $0.03/lb overwrites the PO $0.04/lb or a pallet tare convention is replaced by a truck-scale tare.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-007` / NOT_RUN.

### BRS-EXP-11-R008: Cross-check physical documents, not guessed shipping completion

**LOCKED · P1 · owner: `plasticos_documents evidence; native Stock/Logistics movement owners`.** Reconcile shipper completion email, loading spreadsheet and signed scale ticket on exact PO, booking, load index, date, container, seal, pieces, gross/tare/net and document identities. Physical weights and counts are evidence candidates, not necessarily invoice weight or legal verified gross mass. If reported identifiers/quantities conflict, preserve all versions, produce an exception and forbid unauthorized state advancement.

- **Positive:** Workbook gives Load 1, PO 64014, booking 6509024800, container CSNU8490558, 20 bales, seal 7695652, 40200 lb; ticket 1728952 confirms gross 72200, tare 32000, net 40200.
- **Negative:** AI silently treats scale ticket $1206 total as the approved PO value or marks ocean departure from the shipper email.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-008` / NOT_RUN.

### BRS-EXP-11-R009: Track externally hosted photos and document completeness honestly

**LOCKED · P1 · owner: `Native Documents original/linked assets; plasticos_documents requirement verdict`.** Capture applicable loading-picture checklist from PO/booking, identify original pictures and external-link references, and show available, missing, inaccessible and verified status separately. Requirements may differ by PO and booking revision; no blanket global photo checklist, storage clone or fabricated proof. Native Documents stores originals or the authorized reference and PlasticOS Documents computes verification.

- **Positive:** The supplier email reports a photo link, but actual photo count/compliance remains pending until the link is accessed and relevant images verified.
- **Negative:** AI marks ten loading photos present and approved merely from a link title BKG 6509024800.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-009` / NOT_RUN.

### BRS-EXP-11-R010: Guard shipment state changes and order balances

**LOCKED · BOTH · owner: `Native Purchase/Sale/Stock and Logistics/Transaction guarded commands`.** Extraction SHALL produce typed event proposals; only the owning business command may advance supplier ready, loaded, pickup, gate accepted, sailed, inventory receipt/delivery or commercial state after all movement-specific checks and idempotency. One approved 40200-lb physical shipment does not complete a 200000-lb/five-container supplier PO, other bookings, or a customer multi-load SO. No direct AI writes to transaction.state or load.state.

- **Positive:** Load 1 recognized, with exact source evidence; the supplier PO retains a remaining balance computed through native order/stock execution and future bookings remain untouched.
- **Negative:** Keyword booking complete causes all five units to close, sale invoice to post, or terminal gate-in to appear.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-010` / NOT_RUN.

### BRS-EXP-11-R011: Propagate only a verified material change to the right consumers

**DESIGN · BOTH · owner: `Export publishes revisions; Logistics/Linda owns schedule/mail`.** When a verified current booking revision changes ERD, cutoff, vessel/voyage, terminal or requested equipment, Export SHALL publish the scoped booking-version delta. Logistics evaluates only impacted physical loads and pending commitments, holds/revalidates stale work orders and exact queued communications, while Linda retains sent and unknown send outcomes. Supplier PO and other sibling bookings remain intact; no automatic carrier booking/rebooking or sending outside authorized Logistics policies.

- **Positive:** Only a load still awaiting gate-in under a verified rolled booking receives an at-risk schedule exception and revised supplier/carrier notice draft after approval.
- **Negative:** AI cancels all five PO loads or regenerates/sends the approved PO automatically from a rolled booking.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-011` / NOT_RUN.

### BRS-EXP-11-R012: Offer a coordinator-style exception and audit view

**DESIGN · BOTH · owner: `Export sourced view + native Activity; Documents and Logistics originals`.** The operator SHALL be able to see which email/PDF/XLSX supplied each field, what changed since the prior booking, who asserted it, whether source is carrier-issued or supplier-reported, confidence and verification status, affected load(s), time-window feasibility, outstanding shipping photos/documents, and the next permitted owner action. Do not create a second case-management system or hidden auto-acceptance.

- **Positive:** A review card shows Old: 1 x 40HQ/ERD Oct 5/Cutoff Oct 9; Candidate: 2 x 40HQ/ERD Oct 26/Cutoff Oct 30, together with booking-identity uncertainty and affected load status.
- **Negative:** A summary displays one clean date, hiding material contradiction and provenance.
- **Related existing BRS:** BRS-EXP-09; BRS-EXP-02; BRS-EXP-10; BRS-POS-02/03/10; exact owner correction needed
- **Acceptance:** `AC-EXP-11-012` / NOT_RUN.
