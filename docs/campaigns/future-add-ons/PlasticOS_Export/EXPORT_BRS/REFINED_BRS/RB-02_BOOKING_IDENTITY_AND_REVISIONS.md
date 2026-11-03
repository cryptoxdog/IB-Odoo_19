# Refined BRS reading brief RB-02: Booking identity and revised carrier terms

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** The booking is the carrier's reservation: it may precede any load, hold several slots and survive changing vessel, schedule or quantity evidence.

## 1. Six governing fields

Use the current sourced Booking No., shipping line, POL, POD, cargo cutoff and ERD as first-class values, never deriving omitted facts from neighboring address fields.

**Canonical rule pointers:** BRS-EXP-02-R002,R003; 13-R001,R002. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Revisions

Recognize same-number updates, increases or reductions in capacity, rolls, cancellations and new replacement numbers; preserve every original and prior accepted state.

**Canonical rule pointers:** BRS-EXP-02-R004; 11-R005,R006. Follow each source rule and its paired acceptance case for exact requirements.

## 3. Context

Distinguish forwarder, carrier, vessel/voyage, terminal, rail ramp, empty pickup, loaded return, official port, ETD/ETA and different cutoff types. Label estimated and actual correctly.

**Canonical rule pointers:** BRS-EXP-13-R003,R004,R006,R007,R009,R010. Follow each source rule and its paired acceptance case for exact requirements.

## 4. Operational truth

Projections draw on accepted bookings and actual owners; industry FOB/FAS labels are not converted automatically into formal Incoterms or a delivery event.

**Canonical rule pointers:** BRS-EXP-02-R005,R006; 13-R008. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-02-R001` (BOTH) - Booking-to-order and shipment cardinality independent. Acceptance: `AC-EXP-02-001`.
- `BRS-EXP-02-R002` (BOTH) - Six first-class booking values. Acceptance: `AC-EXP-02-002`.
- `BRS-EXP-02-R003` (BOTH) - ERD and cargo cutoff semantics. Acceptance: `AC-EXP-02-003`.
- `BRS-EXP-02-R004` (BOTH) - Schedule source, revisions and time zones. Acceptance: `AC-EXP-02-004`.
- `BRS-EXP-02-R005` (BOTH) - Operational readiness is a projection. Acceptance: `AC-EXP-02-005`.
- `BRS-EXP-02-R006` (BOTH) - Commercial label is not a legal Incoterm. Acceptance: `AC-EXP-02-006`.
- `BRS-EXP-13-R001` (BOTH) - Primary booking identity and existing six critical fields. Acceptance: `AC-EXP-13-001`.
- `BRS-EXP-13-R002` (BOTH) - Additional independent deadline types and timezone. Acceptance: `AC-EXP-13-002`.
- `BRS-EXP-13-R003` (BOTH) - Carrier, forwarder, vessel, voyage and transport milestones. Acceptance: `AC-EXP-13-003`.
- `BRS-EXP-13-R004` (BOTH) - Port versus receipt, delivery and terminal locations. Acceptance: `AC-EXP-13-004`.
- `BRS-EXP-13-R006` (BOTH) - Contract references and cargo constraints. Acceptance: `AC-EXP-13-006`.
- `BRS-EXP-13-R007` (BOTH) - Optional commercial group and current booking status. Acceptance: `AC-EXP-13-007`.
- `BRS-EXP-13-R008` (BOTH) - AI extraction fills only exact authoritative targets. Acceptance: `AC-EXP-13-008`.
- `BRS-EXP-13-R009` (BOTH) - Native-first ergonomic booking form and tabs. Acceptance: `AC-EXP-13-009`.
- `BRS-EXP-13-R010` (BOTH) - Carrier document and operator-generated booking distinction. Acceptance: `AC-EXP-13-010`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.
