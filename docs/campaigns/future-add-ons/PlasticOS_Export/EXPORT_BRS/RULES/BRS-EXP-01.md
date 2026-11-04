# BRS-EXP-01: Native-first boundaries and minimality

**Class:** additive design rules; distinct from existing `BRS-POS-*` chapters.
**Primary semantic owner:** Export product owner, subject to existing native owners
**Authority:** previously operator-locked scope is LOCKED; unapproved technical recommendations are DESIGN. This is an unadmitted planning artifact.
**Phases:** P1 = recycler FOB/FAS; P2 = actual international seller; BOTH = shared.
**Runtime and independent acceptance:** NOT_RUN.

## Rules

### BRS-EXP-01-R001: Thin export scope

**LOCKED · BOTH · owner: `plasticos_export`.** `plasticos_export` SHALL own only the missing export-specific booking/shipment context, applicability declarations, views and QWeb report layouts; it SHALL first inspect and reuse existing Odoo/PlasticOS records and SHALL NOT recreate storage, a logistics/dispatch engine, inventory, finance, or a shared document-compliance engine.

- **Positive:** An FAS booking is shown with native linked SO/PO, load, evidence and reports; every new export field has a reason for not reusing an existing field.
- **Negative:** New export `stock.move`, `mail.queue`, `document.file` or generic `compliance_status` authority is introduced.
- **Related existing BRS:** BRS-POS-01-R001..R003,R010.
- **Acceptance:** `AC-EXP-01-001` / NOT_RUN.

### BRS-EXP-01-R002: Single authoritative fact owner

**LOCKED · BOTH · owner: `existing native and domain owners`.** Original bytes/versions belong to native Odoo Documents or approved `ir.attachment` fallback; business evidence classification/verification belong to `plasticos_documents`; purchase/sales and financial facts belong to native Odoo; stock movements belong to native Stock; freight, dispatch and approved external operational mail belong to `plasticos_logistics`/Linda. Export SHALL only bind and display those facts.

- **Positive:** Export view shows one current document verdict, one freight status, one stock movement and one posted invoice sourced from the proper owners.
- **Negative:** Export stores a second verified flag, shipment stock quantity, actual freight ledger or independently sent mail.
- **Related existing BRS:** BRS-POS-01-R002,R009; BRS-POS-02-R001; BRS-POS-03-R004.
- **Acceptance:** `AC-EXP-01-002` / NOT_RUN.

### BRS-EXP-01-R003: Exact associations without mandatory early buyer

**LOCKED · BOTH · owner: `Export binding; native commercial owners`.** All export bookings, sale/purchase order lines, loads, documents, packages and containers SHALL be linked by exact company and typed identity, not guessed partner/name/newest record. A supplier-backed load or owned in-transit inventory MAY have no assigned buyer or sales order until a real sale occurs, subject to the approved procurement/movement authority. An actual customer sale SHALL retain its real buyer. No artificial buyer, sales order, transaction or stock picking SHALL be created merely to satisfy a foreign-key or dispatch constraint.

- **Positive:** A company buys and dispatches an approved supplier load with buyer unset; it is held as unallocated stock/in-transit material and later linked to a genuine buyer sale with audit history.
- **Negative:** An AI booking auto-link picks the newest transaction from the same supplier, or the dispatcher creates a dummy buyer to proceed.
- **Related existing BRS:** BRS-EXP-08-R001,R007; BRS-POS-05; Logistics BRS-01 owner delta.
- **Acceptance:** `AC-EXP-01-003` / NOT_RUN.

### BRS-EXP-01-R004: Evidence proposals are not unauthorized business transitions

**LOCKED · BOTH · owner: `native state owner; authorized tool command`.** Saving or extracting a booking, receiving a file, scanning, or generating a report SHALL NOT directly set a purchase, sale, transaction, stock, load, compliance, financial or regulatory state. A verified source observation MAY request a *named, authorized* state-owner business action if exact scope, preconditions, idempotency, and actor permissions are satisfied. The authoritative owner SHALL enforce the transition and return accepted/refused with reason and provenance; no direct state write or bypass is allowed.

- **Positive:** An exactly matched, verified booking updates its booking context; an explicitly permitted documented transition is performed only through an authorized guarded business action.
- **Negative:** AI marks transaction delivered/invoiced when it reads a booking PDF, or a controller writes `state` directly.
- **Related existing BRS:** BRS-EXP-09-R006,R007; BRS-POS-01-R009; BRS-POS-10.
- **Acceptance:** `AC-EXP-01-004` / NOT_RUN.

### BRS-EXP-01-R005: Capability proof and deployment independence

**DESIGN · BOTH · owner: `Odoo deployment/license owner`.** Before depending on Enterprise Documents, Inventory Barcode, AI/OCR or IoT device features, installation, licensing and actual installed API SHALL be verified; where the approved build lacks a capability, Export SHALL use an explicitly approved native fallback or keep it unavailable rather than fabricate or silently require it.

- **Positive:** A CE environment records its supported attachment workflow and marks Enterprise-only features unavailable.
- **Negative:** Export refuses to install because a speculative Documents AI action is mandatory or claims scanning was proven.
- **Related existing BRS:** BRS-POS-01-R006; BRS-POS-02-R010; BRS-POS-09-R016.
- **Acceptance:** `AC-EXP-01-005` / NOT_RUN.
