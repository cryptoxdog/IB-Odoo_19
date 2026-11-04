# Refined BRS reading brief RB-07: Phase 2 international selling and provider boundaries

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** Extend existing shipment identity for ocean sale and compliance assistance; do not make external APIs prerequisites for a domestic-to-port Phase 1.

## 1. Commercial voyage

In-transit genuine sale, freight-inclusive CNF/CFR/CIF and distinct insurance, carriage, payment and legal handoff rules.

**Canonical rule pointers:** BRS-EXP-05-R001,R002,R006. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Ocean paperwork

Existing Documents owns carrier-issued ocean B/L, instructions, verified VGM and responsible-party filing evidence. Any sourced milestone remains independent of load dispatch.

**Canonical rule pointers:** BRS-EXP-05-R003,R004,R005. Follow each source rule and its paired acceptance case for exact requirements.

## 3. FindTEU

Optional container/booking tracking, observed vessel/terminal events and ETAs with provenance, stale updates and rollout exceptions. No source-owned business state takeover.

**Canonical rule pointers:** BRS-EXP-12-R001,R002,R003,R004,R005; 14-R013. Follow each source rule and its paired acceptance case for exact requirements.

## 4. AESDirect

Authorize filing preparation, reviewable official portal/WebLink/bulk handoff, ITN and revisions. Do not claim certified direct filing or invent a government filing success.

**Canonical rule pointers:** BRS-EXP-12-R006,R007,R008,R009,R010. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-05-R001` (P2) - In-transit sale reuses original shipment and evidence. Acceptance: `AC-EXP-05-001`.
- `BRS-EXP-05-R002` (P2) - Freight-inclusive price/role semantics. Acceptance: `AC-EXP-05-002`.
- `BRS-EXP-05-R003` (P2) - Ocean milestones are sourced facts. Acceptance: `AC-EXP-05-003`.
- `BRS-EXP-05-R004` (P2) - Ocean B/L, shipping instructions and VGM. Acceptance: `AC-EXP-05-004`.
- `BRS-EXP-05-R005` (P2) - Applicable regulated filings and filing actors. Acceptance: `AC-EXP-05-005`.
- `BRS-EXP-05-R006` (P2) - Phase 2 operations remain native-first. Acceptance: `AC-EXP-05-006`.
- `BRS-EXP-12-R001` (P2) - FindTEU Phase 2 tracking adapter. Acceptance: `AC-EXP-12-001`.
- `BRS-EXP-12-R002` (P2) - Exact container identity and optional booking-number tracking. Acceptance: `AC-EXP-12-002`.
- `BRS-EXP-12-R003` (P2) - Carrier observation is not commercial or stock authority. Acceptance: `AC-EXP-12-003`.
- `BRS-EXP-12-R004` (P2) - Rolls, replay, reversals and provider discrepancies. Acceptance: `AC-EXP-12-004`.
- `BRS-EXP-12-R005` (P2) - FindTEU tenancy, credentials, outages and coverage gate. Acceptance: `AC-EXP-12-005`.
- `BRS-EXP-12-R006` (P2) - AESDirect Phase 2 EEI filing support, not autonomous filing. Acceptance: `AC-EXP-12-006`.
- `BRS-EXP-12-R007` (P2) - Validate and assemble filing data from existing business sources. Acceptance: `AC-EXP-12-007`.
- `BRS-EXP-12-R008` (P2) - Official AESDirect portal, WebLink or supported bulk handoff. Acceptance: `AC-EXP-12-008`.
- `BRS-EXP-12-R009` (P2) - Official response, ITN or exemption evidence and errors. Acceptance: `AC-EXP-12-009`.
- `BRS-EXP-12-R010` (P2) - Amendments, cancellations, access control and certification boundary. Acceptance: `AC-EXP-12-010`.
- `BRS-EXP-14-R013` (P2) - Phase 2 provider evidence is additive. Acceptance: `AC-EXP-14-013`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.
