# Refined BRS reading brief RB-01: Commercial truth and architectural authority

**Class:** Non-normative implementation reading projection. **Authority:** original stable `BRS-EXP-*` rules in `RULES/`. **Conformance:** original `ACCEPTANCE/cases.json`. **Runtime:** NOT_RUN.

**Operator purpose:** One approved commercial order can produce many exact partial shipments; the buyer may be assigned later, but ownership and company never become hypothetical.

## 1. Independent commitments

Purchase and Sales authorize their own real orders and partial quantities; linking a booking does not issue, cancel, confirm or invoice an order.

**Canonical rule pointers:** BRS-EXP-01-R001,R002,R003; 08-R001,R002,R003,R004,R007,R008. Follow each source rule and its paired acceptance case for exact requirements.

## 2. Distinct identities

Shipment transaction, physical load, booking reservation and actual ISO container never collapse into one object; where the existing one-transaction/one-load representation works, retain it.

**Canonical rule pointers:** BRS-EXP-02-R001; 08-R005,R006. Follow each source rule and its paired acceptance case for exact requirements.

## 3. Buyer and destination

An actual sale has its real buyer; a legitimate purchased/owned load may have none yet. A buyer, delivery terminal, carrier and custody owner are different facts.

**Canonical rule pointers:** BRS-EXP-01-R003; 04-R003; 06-R003. Follow each source rule and its paired acceptance case for exact requirements.

## 4. Safety and financial boundaries

Company/party ACLs, native financial posting, proper weights and real source prerequisites govern every read and command. An extracted document has no authority to change those rules.

**Canonical rule pointers:** BRS-EXP-01-R004,R005; 06-R001,R002,R004,R005. Follow each source rule and its paired acceptance case for exact requirements.

## Exact primary source IDs for this concern

- `BRS-EXP-01-R001` (BOTH) - Thin export scope. Acceptance: `AC-EXP-01-001`.
- `BRS-EXP-01-R002` (BOTH) - Single authoritative fact owner. Acceptance: `AC-EXP-01-002`.
- `BRS-EXP-01-R003` (BOTH) - Exact associations without mandatory early buyer. Acceptance: `AC-EXP-01-003`.
- `BRS-EXP-01-R004` (BOTH) - Evidence proposals are not unauthorized business transitions. Acceptance: `AC-EXP-01-004`.
- `BRS-EXP-01-R005` (BOTH) - Capability proof and deployment independence. Acceptance: `AC-EXP-01-005`.
- `BRS-EXP-06-R001` (BOTH) - Audience/confidentiality and company isolation. Acceptance: `AC-EXP-06-001`.
- `BRS-EXP-06-R002` (BOTH) - Unknown and contradictory evidence remains visible. Acceptance: `AC-EXP-06-002`.
- `BRS-EXP-06-R003` (BOTH) - Order, shipment, evidence and transaction states remain scoped. Acceptance: `AC-EXP-06-003`.
- `BRS-EXP-06-R004` (BOTH) - Minimality and acceptance gate. Acceptance: `AC-EXP-06-004`.
- `BRS-EXP-06-R005` (BOTH) - Safe change and activation boundaries. Acceptance: `AC-EXP-06-005`.
- `BRS-EXP-08-R001` (BOTH) - Buyer optional before a genuine sale. Acceptance: `AC-EXP-08-001`.
- `BRS-EXP-08-R002` (BOTH) - One large customer commitment with smaller supply orders. Acceptance: `AC-EXP-08-002`.
- `BRS-EXP-08-R003` (BOTH) - Partial purchase fulfillment without PO duplication. Acceptance: `AC-EXP-08-003`.
- `BRS-EXP-08-R004` (BOTH) - Partial sales fulfillment and reserved allocation. Acceptance: `AC-EXP-08-004`.
- `BRS-EXP-08-R007` (BOTH) - Late buyer assignment and on-water resale. Acceptance: `AC-EXP-08-007`.
- `BRS-EXP-08-R008` (BOTH) - Movement eligibility by purpose, not a universal buyer predicate. Acceptance: `AC-EXP-08-008`.

**Design boundary:** Any conflict or new field must be resolved at its source owner, without editing the frozen Export meaning inside this condensed reading brief.
