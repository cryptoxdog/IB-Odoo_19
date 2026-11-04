# Refined BRS reading brief RB-05: Physical logistics and handoff

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** Export provides booking requirements, Logistics decides whether and how an actual inland movement can be dispatched.

## 1. FOB/FAS operating modes

Treat trade FOB pickup and trade FAS delivery to terminal/rail as operational descriptions; preserve actual freight arranger/payer and named handoff terms separately.

**Canonical rule pointers:** BRS-EXP-04-R001,R002,R003. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Readiness window

ERD and cargo cutoff restrict terminal acceptance, not supplier loading start. Feasibility uses actual supplier hours, load duration, appointments, transit and authorized staging.

**Canonical rule pointers:** BRS-EXP-04-R004; 10-R001,R005. Follow each source rule and its paired acceptance case for exact requirements.

## 3. Independent release and packets

Issue a genuine approved PO before booking if needed; send a later booking separately. Only for operator-arranged drayage issue an audience-safe current work order and carrier booking packet through Linda.

**Canonical rule pointers:** BRS-EXP-10-R002,R003,R006,R008. Follow each source rule and its paired acceptance case for exact requirements.

## 4. Changed instructions

Material carrier revisions invalidate only affected commitments and pending communications; no automatic new tender, rate or dispatch. Arrival, gate-in, vessel loading and departure have distinct evidence.

**Canonical rule pointers:** BRS-EXP-10-R004,R007. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-04-R001` (P1) - FOB buyer pickup as industry operation. Acceptance: `AC-EXP-04-001`.
- `BRS-EXP-04-R002` (P1) - FAS inland freight-included delivery. Acceptance: `AC-EXP-04-002`.
- `BRS-EXP-04-R003` (P1) - Physical handoff and commercial allocation are independent. Acceptance: `AC-EXP-04-003`.
- `BRS-EXP-04-R004` (P1) - ERD-to-cutoff dispatch visibility. Acceptance: `AC-EXP-04-004`.
- `BRS-EXP-10-R001` (P1) - Current booking requirements are revision-bound Logistics input. Acceptance: `AC-EXP-10-001`.
- `BRS-EXP-10-R002` (P1) - Independent supplier PO issue and later booking delivery. Acceptance: `AC-EXP-10-002`.
- `BRS-EXP-10-R003` (P1) - Carrier packet: booking and drayage Work Order, audience-safe. Acceptance: `AC-EXP-10-003`.
- `BRS-EXP-10-R004` (P1) - Material amendments protect pending commitments and mail. Acceptance: `AC-EXP-10-004`.
- `BRS-EXP-10-R005` (P1) - ERD and cutoff are terminal constraints, not supplier pickup dates. Acceptance: `AC-EXP-10-005`.
- `BRS-EXP-10-R006` (P1) - Equipment-aware freight context and explicit commitments. Acceptance: `AC-EXP-10-006`.
- `BRS-EXP-10-R007` (BOTH) - Terminal and voyage milestones have distinct evidence. Acceptance: `AC-EXP-10-007`.
- `BRS-EXP-10-R008` (P1) - Movement authorization not tied to buyer visibility. Acceptance: `AC-EXP-10-008`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.
