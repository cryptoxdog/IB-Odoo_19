# BRS-EXP-13: Booking form, extended fields and documentary reconciliation

**Scope:** Booking master/UI is a thin view of source-bound export facts; native Odoo owns generic shared data.

**Authority:** New operator-accepted product goals; precise technical implementation remains DESIGN pending repo owner admission.

**Acceptance:** Source-bound fixtures, no live runtime proof; all test outcomes NOT_RUN.

## Rules

### BRS-EXP-13-R001: Primary booking identity and existing six critical fields

**LOCKED · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The Export form SHALL present an authoritative booking identity with booking number, shipping line, POL, POD, cargo cutoff, ERD, plus source document, revision, effective date and exact company scope. No field SHALL be duplicated when its canonical Odoo equivalent already exists.

- **Positive:** Booking 6509024800 shows its six fields and source revision with typed links to the applicable loads and documents.

- **Negative:** POL and POD are conflated, a vendor contact becomes the shipment buyer, or the same booking is stored as two competing records.

- **Related BRS:** BRS-EXP-02-R001; BRS-EXP-09; BRS-EXP-11

- **Acceptance:** `AC-EXP-13-001` / NOT_RUN.

### BRS-EXP-13-R002: Additional independent deadline types and timezone

**LOCKED · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Booking form SHALL distinguish cargo/gate cutoff, documentation cutoff, VGM cutoff, and earliest loaded return; each holds date, time, time zone where known, source/version, and confirmed-versus-proposed status. Missing values remain unset rather than borrowed from another deadline.

- **Positive:** Cargo cutoff 2026-10-12 16:00 PT, documentation cutoff 12:00 PT and VGM cutoff 16:00 PT are independently visible.

- **Negative:** An email changing cargo cutoff silently changes VGM/document deadlines or treats an unconfirmed date as final.

- **Related BRS:** BRS-EXP-02; BRS-EXP-09; BRS-EXP-11

- **Acceptance:** `AC-EXP-13-002` / NOT_RUN.

### BRS-EXP-13-R003: Carrier, forwarder, vessel, voyage and transport milestones

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Export SHALL display shipping line, forwarder/booking agent where applicable, vessel, voyage, estimated/actual ETD and ETA with exact source. Recurring updates SHALL preserve old revisions. Physical arrival or gate-in belongs to Logistics/Stock evidence and is never inferred solely from ETA.

- **Positive:** COSCO, TOP POINT PLASTICS, CMA CGM JEAN GABRIEL, MTE0, ETA and ETD are mapped to distinct sourced fields.

- **Negative:** One ETA update marks vessel arrival as actual or overwrites a verified terminal acceptance event.

- **Related BRS:** BRS-EXP-02; BRS-EXP-11; BRS-EXP-12

- **Acceptance:** `AC-EXP-13-003` / NOT_RUN.

### BRS-EXP-13-R004: Port versus receipt, delivery and terminal locations

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Export SHALL distinguish POL, POD, place of receipt, final place of delivery, empty container pickup facility, loaded container return terminal and rail ramp. Export publishes applicable booking constraints; Logistics owns actual pickup, terminal appointments and execution.

- **Positive:** Long Beach as POL, Port Klang as POD, PCT as empty pickup and APL as loaded return remain four distinct concepts.

- **Negative:** The buyer address is silently selected as terminal destination or a POL location substitutes for a physical drayage gate.

- **Related BRS:** BRS-EXP-02; BRS-EXP-10

- **Acceptance:** `AC-EXP-13-004` / NOT_RUN.

### BRS-EXP-13-R005: Equipment quantity and multiple independent container identities

**LOCKED · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Export SHALL show requested equipment type and quantity at booking level and actual container number, seal, physical load, supplier PO, transaction and observed weights at container level. One ocean booking may include multiple supplier POs, multiple trade transactions and containers; allocation is exact and reversible.

- **Positive:** Booking 6509024800 contains five 40HC containers from four supplier POs, each retaining its own container/seal/weights.

- **Negative:** The system forces one PO per ocean booking or duplicates a single physical container into five transaction loads.

- **Related BRS:** BRS-EXP-07; BRS-EXP-08; BRS-EXP-11

- **Acceptance:** `AC-EXP-13-005` / NOT_RUN.

### BRS-EXP-13-R006: Contract references and cargo constraints

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** The booking form SHALL expose reference numbers (order, house/master bill where supported), booking date, booking contact, cargo description, classification code when evidenced, and contractual minimum/maximum cargo weights; use native product/partner/quantity models as canonical owners. Weight constraints never authoritatively rewrite actual or invoiced weight.

- **Positive:** Cargo weight limits display alongside, not as replacements for, verified 40,200-lb load net weight.

- **Negative:** An AI-extracted description or blank weight constraint modifies the stock quant, invoice or purchase price.

- **Related BRS:** BRS-EXP-07; BRS-EXP-11

- **Acceptance:** `AC-EXP-13-006` / NOT_RUN.

### BRS-EXP-13-R007: Optional commercial group and current booking status

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Booking date, contact, optional group, forwarder, agreement/reference and booking confirmation status SHALL be displayed when source-backed. Status must distinguish requested, confirmed, revised, rolled, cancelled, expired and partially fulfilled where those semantics are evidenced; do not infer confirmation from UI display or email timestamp.

- **Positive:** A booking-roll email creates reviewable revised status with old original preserved; a blank Group stays blank.

- **Negative:** Any email containing the booking number automatically marks all containers accepted by terminal.

- **Related BRS:** BRS-EXP-11

- **Acceptance:** `AC-EXP-13-007` / NOT_RUN.

### BRS-EXP-13-R008: AI extraction fills only exact authoritative targets

**DESIGN · BOTH · owner: `plasticos_documents + native Odoo AI/Document owners; Export consumes validated candidates`.** Native Odoo 19 AI Documents may extract booking-form fields from emails, PDFs, and spreadsheets with page/message/field provenance. Existing `plasticos_documents` resolves exact booking, company, PO, transaction, container and revision before an authorized export action writes permitted fields. Ambiguous or material conflicts require review; AI must not set physical, commercial or financial states directly.

- **Positive:** A revised 5x40HC email is associated with the existing booking and produces a field-by-field approved comparison before deadline update.

- **Negative:** A newest-open-by-partner guess links an amended booking to another PO, or extracted ETA directly closes a sale.

- **Related BRS:** BRS-EXP-09; BRS-EXP-11

- **Acceptance:** `AC-EXP-13-008` / NOT_RUN.

### BRS-EXP-13-R009: Native-first ergonomic booking form and tabs

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Booking presentation SHALL use Odoo form, smart buttons/related records and standard tabbed views for Shipments, Order Allocation, Instructions, Budget Expenses and Documentation only where there is an existing authoritative source; tabs must not host duplicate ledger, document, logistics or accounting data.

- **Positive:** An operator opens one booking and navigates to five assigned containers, four POs, verified documents and native freight records.

- **Negative:** A Budget Expenses tab creates a second freight or AP ledger or Documents tab creates another verification field.

- **Related BRS:** BRS-EXP-01; BRS-EXP-06

- **Acceptance:** `AC-EXP-13-009` / NOT_RUN.

### BRS-EXP-13-R010: Carrier document and operator-generated booking distinction

**DESIGN · BOTH · owner: `plasticos_export; native Odoo owns shared commercial and logistics facts`.** Export SHALL distinguish a carrier/forwarder original booking confirmation from an export-generated booking report/supplier summary. Files belong to native Documents, verification to PlasticOS Documents and communications to Linda; the form may expose print/send actions only through these owners.

- **Positive:** Original carrier PDF and audience-safe supplier summary are both linked, labeled and separately versioned.

- **Negative:** A generated PDF carries carrier-issued claims or Export sends supplier email directly via an alternate mail queue.

- **Related BRS:** BRS-EXP-03; BRS-EXP-10

- **Acceptance:** `AC-EXP-13-010` / NOT_RUN.
