# BRS-EXP-03: Document applicability, evidence and reporting

**Class:** additive design rules; distinct from existing `BRS-POS-*` chapters.
**Primary semantic owner:** plasticos_export context with existing Documents and Linda owners
**Authority:** previously operator-locked scope is LOCKED; unapproved technical recommendations are DESIGN. This is an unadmitted planning artifact.
**Phases:** P1 = recycler FOB/FAS; P2 = actual international seller; BOTH = shared.
**Runtime and independent acceptance:** NOT_RUN.

## Rules

### BRS-EXP-03-R001: Native intake, AI-proposed extraction and exact document attribution

**LOCKED · BOTH · owner: `native Documents intake; plasticos_documents exact evidence link`.** Booking confirmations, amendments, gate receipts, emails and other originals SHALL enter through native Documents/approved attachments and retain original bytes, versions and attributable metadata. Odoo 19 AI document facilities MAY extract proposed typed booking values and candidate relations, but SHALL NOT auto-commit a partner-only or newest-open-record guess. The document owner SHALL resolve the exact company, booking, intended physical shipment and valid revision (or hold for review) before Export consumes facts; no duplicate original store or verifier.

- **Positive:** Four weekly bookings from the same Charleston supplier are independently extracted and attached to their correct load/booking without cross-linking.
- **Negative:** AI auto-sort associates each document with the latest open transaction for Waste Management or silently replaces the original.
- **Related existing BRS:** BRS-EXP-09-R001..R005; BRS-POS-02-R001,R007; BRS-POS-03-R002.
- **Acceptance:** `AC-EXP-03-001` / NOT_RUN.

### BRS-EXP-03-R002: Applicability belongs to export, verdict to Documents

**LOCKED · BOTH · owner: `export applicability / `plasticos_documents` verification`.** Export SHALL declare which document categories are required for the specific booking, phase, agreement, party, stage and requested operation. `plasticos_documents` SHALL own whether exact current evidence meets those requirements and whether an authorized override applies. Export SHALL consume that verdict, never author its own verified/compliant status or second rule evaluator.

- **Positive:** Phase 1 FAS requires terminal gate receipt for a particular handoff; Documents says missing until verified current evidence arrives.
- **Negative:** Any upload unconditionally flips an export `documents_complete` stored flag despite invalid source evidence.
- **Related existing BRS:** BRS-POS-03-R004..R007.
- **Acceptance:** `AC-EXP-03-002` / NOT_RUN.

### BRS-EXP-03-R003: No duplicate verification action

**LOCKED · BOTH · owner: ``plasticos_documents``.** Native Documents UI/actions SHALL delegate business verification, refusal and override to one approved `plasticos_documents` owner with attributable actor, source/version and scope; Export SHALL be read-only for the verification result. Existing duplicated native `verified` actions SHALL be reconciled at the Documents owner before Export relies on their output.

- **Positive:** Native view and PlasticOS evidence show one identical approved verdict.
- **Negative:** Native verify button writes its own independent verified truth and Export accepts it without the business owner.
- **Related existing BRS:** BRS-POS-03-R004,R005; observed existing Documents seam.
- **Acceptance:** `AC-EXP-03-003` / NOT_RUN.

### BRS-EXP-03-R004: Native export-specific reports

**LOCKED · BOTH · owner: `plasticos_export QWeb layout / native source values`.** Export MAY own only export-specific QWeb report templates and view composition (booking/dispatch sheet, container/package packing list, exceptions, outbound document packet). Data SHALL come from the current native sales, stock, logistics, booking and verified Documents owners; reports SHALL be version-aware, audience-safe and shall not impersonate a third-party issued B/L or certification.

- **Positive:** Booking sheet and packing list print exact booking revision and native package weights without changing inventory.
- **Negative:** Generating a packing list overwrites actual stock weight or forges a carrier-issued ocean B/L.
- **Related existing BRS:** BRS-POS-10-R003; BRS-POS-11-R004.
- **Acceptance:** `AC-EXP-03-004` / NOT_RUN.

### BRS-EXP-03-R005: Linda owns external sends

**LOCKED · BOTH · owner: ``plasticos_logistics` / Linda using native Odoo Mail`.** An export screen MAY request an authorized outgoing report, booking reply, document request or amendment through the approved existing Linda/Odoo Mail operation. Export SHALL NOT send, retry, chase, or separately schedule the same external correspondence; queued, sent and unknown delivery outcomes SHALL remain distinct and attributable.

- **Positive:** One report is sent once with approved recipient/edition and Odoo mail evidence.
- **Negative:** Export calls its own SMTP or resends a message whose delivery status is unknown while Linda is also sending.
- **Related existing BRS:** BRS-POS-09-R006; BRS-POS-10-R004,R005,R015.
- **Acceptance:** `AC-EXP-03-005` / NOT_RUN.

### BRS-EXP-03-R006: Missing documents use existing activity owners

**DESIGN · BOTH · owner: ``plasticos_documents`/native Activity; Linda external reminders`.** A missing or invalid export-required file SHALL appear as one scoped Documents compliance exception and the appropriate native internal Activity/Request; any approved external chase uses the existing Linda obligation and native scheduler. Export SHALL NOT add a recurring document-chase cron or another reminder ledger.

- **Positive:** Missing gate receipt generates one internal review item and, if explicitly approved, a single Linda outreach episode.
- **Negative:** Documents, Export and Linda each send a separate external request for the same receipt.
- **Related existing BRS:** BRS-POS-09-R003,R005,R006,R012.
- **Acceptance:** `AC-EXP-03-006` / NOT_RUN.

### BRS-EXP-03-R007: Correct document type and actual obligation

**DESIGN · BOTH · owner: `export applicability / document type owner`.** The required file set SHALL depend on actual booking, cargo, contract, destination/transit jurisdiction and responsible party; Phase 1 shall not require every Phase 2 ocean document. Domestic truck BOL, carrier-issued ocean B/L, verified gross mass evidence, commercial invoice and filings SHALL be separately classified and attributed; a file received is not a valid approval merely by existing.

- **Positive:** A port/rail FAS sale is eligible for terminal handoff review without a fictitious issued ocean B/L when its actual obligation does not require one.
- **Negative:** An export-ready badge assumes every BOL is an issued ocean B/L or unconditionally demands foreign customs paperwork in Phase 1.
- **Related existing BRS:** BRS-POS-03-R001,R007.
- **Acceptance:** `AC-EXP-03-007` / NOT_RUN.
