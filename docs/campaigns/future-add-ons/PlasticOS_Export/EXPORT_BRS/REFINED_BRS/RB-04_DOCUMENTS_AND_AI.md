# Refined BRS reading brief RB-04: Documents, AI and evidence

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** The AI reads real supplier/carrier correspondence as a coordinator would. It does not become a second verifier or make authoritative order or shipment transitions.

## 1. Original and applicability

Native Documents receives originals and versions; Export declares document applicability; PlasticOS Documents decides current business verification.

**Canonical rule pointers:** BRS-EXP-03-R001,R002,R003,R007. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Precise extraction

Email body plus PDFs, workbooks, scale tickets and photo references yield source-attributed candidate fields with exact company, PO/SO, booking, load and container identity.

**Canonical rule pointers:** BRS-EXP-09-R001,R002,R003; 11-R001,R002,R003,R004. Follow each source rule and its paired acceptance case for exact requirements.

## 3. Revision/reconciliation

Conflicts and rolled bookings are held for explicit resolution; repeated delivery is idempotent; verified weights/invoices do not follow automatically from scanned numbers.

**Canonical rule pointers:** BRS-EXP-09-R004,R005,R006; 11-R005,R006,R007,R008,R009. Follow each source rule and its paired acceptance case for exact requirements.

## 4. Commands and exceptions

Only domain-owner validated actions may change states; Linda handles external requests; internal missing-doc activities are existing native Activities, not a new workflow engine.

**Canonical rule pointers:** BRS-EXP-03-R005,R006; 09-R007,R008; 11-R010,R011,R012. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-03-R001` (BOTH) - Native intake, AI-proposed extraction and exact document attribution. Acceptance: `AC-EXP-03-001`.
- `BRS-EXP-03-R002` (BOTH) - Applicability belongs to export, verdict to Documents. Acceptance: `AC-EXP-03-002`.
- `BRS-EXP-03-R003` (BOTH) - No duplicate verification action. Acceptance: `AC-EXP-03-003`.
- `BRS-EXP-03-R004` (BOTH) - Native export-specific reports. Acceptance: `AC-EXP-03-004`.
- `BRS-EXP-03-R005` (BOTH) - Linda owns external sends. Acceptance: `AC-EXP-03-005`.
- `BRS-EXP-03-R006` (BOTH) - Missing documents use existing activity owners. Acceptance: `AC-EXP-03-006`.
- `BRS-EXP-03-R007` (BOTH) - Correct document type and actual obligation. Acceptance: `AC-EXP-03-007`.
- `BRS-EXP-09-R001` (BOTH) - Use Odoo native AI Documents before custom extraction. Acceptance: `AC-EXP-09-001`.
- `BRS-EXP-09-R002` (BOTH) - Typed field extraction with source-level provenance. Acceptance: `AC-EXP-09-002`.
- `BRS-EXP-09-R003` (BOTH) - Exact company-and-booking match, never latest partner. Acceptance: `AC-EXP-09-003`.
- `BRS-EXP-09-R004` (BOTH) - Ambiguity, conflicting originals and correction review. Acceptance: `AC-EXP-09-004`.
- `BRS-EXP-09-R005` (BOTH) - Version-safe, idempotent apply. Acceptance: `AC-EXP-09-005`.
- `BRS-EXP-09-R006` (BOTH) - Apply structured values only through approved owner interface. Acceptance: `AC-EXP-09-006`.
- `BRS-EXP-09-R007` (BOTH) - Transaction/load state changes only via validated commands. Acceptance: `AC-EXP-09-007`.
- `BRS-EXP-09-R008` (BOTH) - Source-scoped status and human review observability. Acceptance: `AC-EXP-09-008`.
- `BRS-EXP-11-R001` (BOTH) - Interpret the whole business correspondence package. Acceptance: `AC-EXP-11-001`.
- `BRS-EXP-11-R002` (BOTH) - Recognize document and message function, not just keywords. Acceptance: `AC-EXP-11-002`.
- `BRS-EXP-11-R003` (BOTH) - Resolve booking-versus-PO-versus-physical load identities. Acceptance: `AC-EXP-11-003`.
- `BRS-EXP-11-R004` (P1) - Extract original booking attributes and missing-field truth. Acceptance: `AC-EXP-11-004`.
- `BRS-EXP-11-R005` (BOTH) - Capture roll reasons, classifications, capacity and continuity. Acceptance: `AC-EXP-11-005`.
- `BRS-EXP-11-R006` (BOTH) - Maintain field-level current value, version, and approval. Acceptance: `AC-EXP-11-006`.
- `BRS-EXP-11-R007` (P1) - Use PO-level terms as constraints without copying financial values. Acceptance: `AC-EXP-11-007`.
- `BRS-EXP-11-R008` (P1) - Cross-check physical documents, not guessed shipping completion. Acceptance: `AC-EXP-11-008`.
- `BRS-EXP-11-R009` (P1) - Track externally hosted photos and document completeness honestly. Acceptance: `AC-EXP-11-009`.
- `BRS-EXP-11-R010` (BOTH) - Guard shipment state changes and order balances. Acceptance: `AC-EXP-11-010`.
- `BRS-EXP-11-R011` (BOTH) - Propagate only a verified material change to the right consumers. Acceptance: `AC-EXP-11-011`.
- `BRS-EXP-11-R012` (BOTH) - Offer a coordinator-style exception and audit view. Acceptance: `AC-EXP-11-012`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.
