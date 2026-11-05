# ADR-014: Architecture boundary tests are release gates

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Behavioral tests verify that the right answer comes out. They cannot detect
that the right answer was produced by the wrong layer. A shadow transport
passes every output assertion — that is why it survived.

## Options Considered

### Option A: Executable ownership guards in CI (chosen)
- Pros: the boundary is enforced continuously rather than at review; a
  regression is caught at the commit that introduces it, naming the file.
- Cons: static guards can produce false positives and need maintained
  allowlists for legitimate sites.

### Option B: Code review and documentation
- Pros: no false positives; understands intent.
- Cons: the shadow SDK was built and merged under review. Documentation does
  not fail a build.

## Decision

Tests must verify architectural ownership, not only output behavior.
IB-Odoo_19 must have tests or static checks that reject production code
bypassing the SDK boundary.

Guard against: direct `/v1/execute` usage; manual Gate HTTP; manual
`TransportPacket` hashing; manual signing; manual transport validation; peer
worker URLs; Odoo retry loops around Gate; duplicate packet builders.

Required test classes:

| Class | Asserts |
|---|---|
| Domain contract | `res.partner` → canonical EnrichRequest |
| Identity | `entity.id`; logical operation identity |
| Invocation | Odoo domain service → actual Gate_SDK public API |
| Response | EnrichResponse → Odoo proposal/writeback mapping |
| Boundary | no prohibited transport implementation in Odoo |
| Runtime | real Odoo 19 + installed Gate_SDK |

## Consequences

- These checks are release gates, not advisory lint.
- An allowlisted site (the single canonical bridge) is named explicitly in the
  guard, so widening it is a reviewable diff rather than an invisible drift.
