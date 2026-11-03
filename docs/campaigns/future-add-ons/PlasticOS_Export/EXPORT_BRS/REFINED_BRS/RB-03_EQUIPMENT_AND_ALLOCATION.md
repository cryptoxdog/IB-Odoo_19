# Refined BRS reading brief RB-03: Equipment, capacity, and load allocation

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** Space in a confirmed ocean booking is a scarce capacity commitment; a booking slot is not a physical container and is not automatically a native stock package.

## 1. Types

40HC common for plastics, 40STD, 45HC, 45STD, 20STD for other trades; domestic 53-foot, 48-foot and flatbed remain road-equipment values, not ocean equipment.

**Canonical rule pointers:** BRS-EXP-07-R001,R002,R003,R005. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Capacity

Booking equipment requirement/count and actual container identity/seal are separate. Requested, confirmed, allocated, loaded and terminal-accepted quantities are independently sourced.

**Canonical rule pointers:** BRS-EXP-07-R004; 13-R005; 14-R014,R015. Follow each source rule and its paired acceptance case for exact requirements.

## 3. Assignments

Allocation is explicit, authorized and revision-safe. Multiple commercial cargo lines within one physical slot count once toward space, and line-level quantities trace to real execution.

**Canonical rule pointers:** BRS-EXP-08-R005,R006; 14-R016,R018. Follow each source rule and its paired acceptance case for exact requirements.

## 4. Safety

Substitutions, equipment limits and weight constraints are exceptions until approved; no nominal container name proves payload limit, VGM, stock or shipment completion.

**Canonical rule pointers:** BRS-EXP-07-R006,R007,R008. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-07-R001` (BOTH) - Equipment vocabulary differentiates road trailers from ocean containers. Acceptance: `AC-EXP-07-001`.
- `BRS-EXP-07-R002` (P1) - Supported domestic trailer choices. Acceptance: `AC-EXP-07-002`.
- `BRS-EXP-07-R003` (BOTH) - Supported ocean container choices with a preference, not a hard constraint. Acceptance: `AC-EXP-07-003`.
- `BRS-EXP-07-R004` (BOTH) - Booking equipment count and per-week physical units. Acceptance: `AC-EXP-07-004`.
- `BRS-EXP-07-R005` (BOTH) - Reuse only the correct equipment owner and native records. Acceptance: `AC-EXP-07-005`.
- `BRS-EXP-07-R006` (BOTH) - Do not infer payload, capacity or VGM from nominal equipment name. Acceptance: `AC-EXP-07-006`.
- `BRS-EXP-07-R007` (BOTH) - Equipment discrepancy and booking amendment are explicit. Acceptance: `AC-EXP-07-007`.
- `BRS-EXP-07-R008` (BOTH) - Reports and loading must use exact units without duplicate inventory. Acceptance: `AC-EXP-07-008`.
- `BRS-EXP-08-R005` (BOTH) - Independent booking per execution and container cardinality. Acceptance: `AC-EXP-08-005`.
- `BRS-EXP-08-R006` (BOTH) - Fulfillment allocation is traceable without second quantity ledger. Acceptance: `AC-EXP-08-006`.
- `BRS-EXP-13-R005` (BOTH) - Equipment quantity and multiple independent container identities. Acceptance: `AC-EXP-13-005`.
- `BRS-EXP-14-R014` (P1) - Booking capacity is equipment-specific and source-confirmed. Acceptance: `AC-EXP-14-014`.
- `BRS-EXP-14-R015` (P1) - One booking slot can serve multiple correctly attributed cargo lines. Acceptance: `AC-EXP-14-015`.
- `BRS-EXP-14-R016` (P1) - Explicit allocation commands respect capacity and revision. Acceptance: `AC-EXP-14-016`.
- `BRS-EXP-14-R018` (P1) - Available bookings and unbooked demand remain distinct. Acceptance: `AC-EXP-14-018`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.
