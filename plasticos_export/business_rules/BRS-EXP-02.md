# BRS-EXP-02: Booking identity, six fields and schedule evidence

**Class:** additive design rules; distinct from existing `BRS-POS-*` chapters.
**Primary semantic owner:** plasticos_export for export-only context
**Authority:** previously operator-locked scope is LOCKED; unapproved technical recommendations are DESIGN. This is an unadmitted planning artifact.
**Phases:** P1 = recycler FOB/FAS; P2 = actual international seller; BOTH = shared.
**Runtime and independent acceptance:** NOT_RUN.

## Rules

### BRS-EXP-02-R001: Booking-to-order and shipment cardinality independent

**DESIGN · BOTH · owner: `plasticos_export booking association; native commercial and Logistics identities`.** A booking SHALL have an authoritative typed company and revision context and MAY relate to one or more physical containers/movements according to the real carrier reservation. One Sales Order or Purchase Order MAY be fulfilled by many loads and distinct bookings; a physical shipment SHALL be linked to its applicable booking and exact order-line/fulfillment allocation without requiring the entire SO or PO to be one shipment. The booking, drayage load, ISO container, seal, stock package/lot and order remain separate identities. A new booking model is conditional on reuse evidence.

- **Positive:** One SO for 30 loads and one supplier PO for four weekly loads can show four separate bookings and individual receipts without duplicating orders or quantities.
- **Negative:** Each new booking clones the PO or SO; the only `transaction.load_id` is overwritten by the fourth physical load.
- **Related existing BRS:** BRS-EXP-08-R002..R006; BRS-POS-05-R004,R007.
- **Acceptance:** `AC-EXP-02-001` / NOT_RUN.

### BRS-EXP-02-R002: Six first-class booking values

**LOCKED · BOTH · owner: `plasticos_export for gaps only`.** Booking No., Steamship Line, Port of Loading, Port of Discharge, Cut Off and Earliest Return Date SHALL be first-class searchable/displayable booking information when supplied; existing authoritative fields SHALL be reused before creating storage. Booking No. remains an unmodified string; Steamship Line SHALL be distinct from forwarder and drayage carrier; POL/POD SHALL be distinct from terminal, rail ramp and final destination.

- **Positive:** An external booking notice supplies all six, and an operator can retrieve it by exact booking number and steamship line.
- **Negative:** A numeric booking field drops leading zeros or Port of Discharge is overwritten with buyer destination.
- **Related existing BRS:** Operator locked export v1.1.0 / v1.2.0.
- **Acceptance:** `AC-EXP-02-002` / NOT_RUN.

### BRS-EXP-02-R003: ERD and cargo cutoff semantics

**LOCKED · BOTH · owner: `plasticos_export schedule context`.** Earliest Return Date SHALL represent the effective earliest permitted loaded-container receiving/gate-in window for the stated booking and facility; Cut Off SHALL represent its stated cargo/terminal acceptance deadline. ERD, cargo cutoff, shipping-instruction cutoff, VGM cutoff, documentation, rail and filing deadlines SHALL remain distinct. A booking without a supplied timestamp SHALL remain date-only or unknown, without invented time-of-day.

- **Positive:** A carrier supplies date-only ERD and an 18:00 terminal-local cargo cutoff; the system keeps their different precision and purpose.
- **Negative:** ERD is misused as the empty-container return date or SI cutoff silently replaces cargo cutoff.
- **Related existing BRS:** Operator locked export v1.1.0; BRS-POS-01-R011.
- **Acceptance:** `AC-EXP-02-003` / NOT_RUN.

### BRS-EXP-02-R004: Schedule source, revisions and time zones

**DESIGN · BOTH · owner: `plasticos_export schedule context + native document provenance`.** Each booking schedule assertion SHALL retain exact source/original reference, reporter, observed time, terminal/local time zone, value precision, effective revision and supersession. A later email SHALL NOT silently overwrite a confirmed cutoff/ERD, and conflicting carrier/terminal notices SHALL remain visible until the responsible party resolves them.

- **Positive:** An amended cutoff preserves both notice originals and displays current confirmed value with its source and timezone.
- **Negative:** Old screenshot silently wins a race against a verified terminal advisory or date-only value becomes 00:00.
- **Related existing BRS:** BRS-POS-02-R007; BRS-POS-03-R006.
- **Acceptance:** `AC-EXP-02-004` / NOT_RUN.

### BRS-EXP-02-R005: Operational readiness is a projection

**DESIGN · BOTH · owner: `plasticos_export view/exception projection`.** Export schedule and readiness views SHALL derive status from current booking evidence, native load/stock status and verified document applicability without becoming a second source of physical or regulatory state. A schedule conflict, missing applicable proof or expired acceptance window SHALL produce an attributed exception; an observed gate event is not automatically legal delivery/risk transfer.

- **Positive:** Cutoff passes with no terminal acceptance record: dashboard shows at-risk/pending and retains source status.
- **Negative:** Booking label changes from Planned to Delivered merely because a cargo cutoff is in the past.
- **Related existing BRS:** BRS-POS-01-R009,R011.
- **Acceptance:** `AC-EXP-02-005` / NOT_RUN.

### BRS-EXP-02-R006: Commercial label is not a legal Incoterm

**LOCKED · BOTH · owner: `native Odoo order/contract + export display`.** The recycler trade labels `FOB` (buyer pickup), `FAS` (seller-included freight to agreed port/rail), and `CNF`/`C&F` SHALL be preserved as quoted business usage separately from any explicitly contracted formal ICC Incoterm and named place. Booking arranger, payer, contracted handoff and exporter/filing role SHALL be explicit facts, not inferred from either shorthand. Export SHALL never silently rewrite an order Incoterm.

- **Positive:** Industry FOB pickup and a formal FCA term can be stored distinctly when the actual contract supports both.
- **Negative:** Selecting FAS sets official ICC FAS risk transfer at rail gate or turns on seller ocean freight automatically.
- **Related existing BRS:** Operator locked v1.2.0; BRS-POS-06-R001.
- **Acceptance:** `AC-EXP-02-006` / NOT_RUN.
