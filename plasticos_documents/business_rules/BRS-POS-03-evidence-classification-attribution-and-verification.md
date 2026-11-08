# BRS-POS-03: Evidence classification, attribution and verification

**Status:** FROZEN WORKING BRS, pending independent repository adoption. No test/code/live authorization.
**Business / semantic owner:** plasticos_documents compliance owner
**Native capabilities and objects:** native Documents fields + existing plasticos.document typed evidence
**Planned implementation lane:** NAT-02 / SAFETY
**Governing baseline:** PlasticOS Primary Campaign Rev008 exact archive digest in `SOURCE_PROVENANCE.json`.
**Status labels:** LOCKED = accepted operator intent or previously accepted business rule; DESIGN = converged working architecture but repository admission pending; CONDITIONAL = require named proof/approval.

## Rules

### BRS-POS-03-R001: One canonical business classification

**DESIGN.** PlasticOS document tag plus party category SHALL be the compliance vocabulary; native classification fields shall project it without becoming a second verifier.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-001`. Native class display and business evidence agree.
- **Required negative control:** A native AI tag independently marks required paperwork compliant.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R002: Typed exact association

**LOCKED.** Each validated evidence link SHALL identify the exact company, transaction/load or PO/picking when appropriate, and applicable source request/version.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-002`. One file attaches to the correct PO-only inbound and later receipt without dummy load.
- **Required negative control:** The same vendor name links a file to an arbitrary open SO.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R003: Multi-record original reuse

**DESIGN.** One original attachment MAY create multiple typed evidence associations when each reference is independently established; this SHALL NOT duplicate its bytes.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-003`. Shared signed freight BOL maps to both legitimate transaction associations with separate references.
- **Required negative control:** One uncertain BOL is marked as proof of every partner load.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R004: Authoritative verification writer

**DESIGN.** Only the approved PlasticOS document verification/override operation SHALL authoritatively set verified, verified_by, verified_at and override evidence, with native views delegating to that owner.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-004`. A native verify action produces one authorized business verification record.
- **Required negative control:** Sync writes verified independently after an OCR event.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R005: Verification is attributable

**LOCKED.** Verification SHALL retain signer/actor, instant, file version, exact party and object, decision and override reason where applicable.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-005`. A revoked document can be traced to its original approval.
- **Required negative control:** An admin changes verification invisibly with no recorded reason.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R006: Expired, inactive or superseded evidence

**DESIGN.** Expired, inactive, superseded, unverified or irrelevant-party evidence SHALL NOT satisfy a required document rule.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-006`. Expiring the sole insurance certificate restores the missing-document obligation.
- **Required negative control:** An old inactive scale file still passes close validation.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R007: Operation-scoped compliance

**LOCKED.** Compliance queries SHALL be read-only and honor operation-specific requirements for invoice, logistics close and dispatch rather than a universal complete flag.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-007`. A missing CST is tracked while verified buyer Receiving permits invoice posting.
- **Required negative control:** A required-for-dispatch document is treated as a buyer-AR block.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R008: No financial side effect from recompute

**LOCKED.** Creating, editing, classifying, verifying or recomputing a document SHALL NOT call account.move.action_post, issue a note, make a payment or create an accounting recovery.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-008`. A verified buyer report leaves draft invoices draft until authorized posting.
- **Required negative control:** Document verification posts all draft vendor and freight bills.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R009: Buyer receiving authority

**LOCKED.** A buyer Receiving Report matched and verified for the correct delivery SHALL be authoritative documentary evidence for buyer invoice eligibility and operational delivery proof.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-009`. The right verified report permits the correct invoice action.
- **Required negative control:** An unverified supplier BOL substitutes for buyer receiving.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R010: Partial receiving attribution

**DESIGN.** A buyer Receiving Report covering only part of an order SHALL not silently authorize an invoice or final close for additional unproven delivered quantities.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-010`. A 20,000-lb verified receipt cannot prove a different 44,000-lb delivered quantity.
- **Required negative control:** One partial report is treated as proof of a whole consolidated shipment.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R011: CST is a distinct carrier obligation

**LOCKED.** Missing carrier certified scale/CST evidence SHALL remain a collection/claim issue; it SHALL NOT block ordinary buyer invoicing or documented commercial close.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-011`. Close with verified Receiving while a missing-CST follow-up remains outstanding.
- **Required negative control:** CST XML required_for_close forces the load to remain open.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R012: Receipt versus certified proof

**DESIGN.** An uploaded scale image SHALL NOT be treated as certified CST without the agreed document form and required fields.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-012`. A photo lacking certification remains a pending evidence issue.
- **Required negative control:** A generic SCALE tag meets carrier certification without inspection.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R013: Human weight capture until extraction admission

**LOCKED.** Authoritative supplier/buyer/scale weights SHALL be entered from verified filed source evidence by an authorized human until a separately admitted extraction capability is proven.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-013`. AI-unavailable intake still permits manual verified weight entry.
- **Required negative control:** An OCR guess overwrites buyer_weight at document upload.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

### BRS-POS-03-R014: Company-aware evidence controls

**LOCKED.** Every evidence relation SHALL preserve the legal company and enforce company-consistent source links and view rights.

- **Native owner:** native Documents fields + existing plasticos.document typed evidence
- **Acceptance:** `AC-POS-03-014`. Different companies with same PO name cannot share document evidence without authorization.
- **Required negative control:** A cross-company document auto-link grants unauthorized visibility.
- **Implementation evidence:** NOT_RUN. No source code, Odoo action or PR created by this BRS pack.

## Design frontier and sources

This chapter uses primary Rev008: CONSOLIDATED_DECISIONS.md, CREDIT_DEBIT_CONVERGENCE_2026-10-25.md, NATIVE_AUTOMATION_ODOO19_ALIGNMENT.md.
No operator-open gate is implicitly closed by a conditional rule. See `GOVERNANCE/OPEN_DECISIONS.md`.
A source/model name is a design candidate until installed Odoo Enterprise evidence validates its exact shape.
