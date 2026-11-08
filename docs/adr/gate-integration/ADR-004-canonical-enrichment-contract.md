# ADR-004: Canonical enrichment contract is EnrichRequest → EnrichResponse

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Two enrichment dialects previously existed around the same `converge` action.
Standardizing transport did not remove that split: the payload semantics could
still drift even while every byte travelled inside a canonical
`TransportPacket`.

## Options Considered

### Option A: One canonical protocol — EnrichRequest → EnrichResponse (chosen)
- Pros: one wire contract owned by EIE; Odoo maps to and from it; schema
  changes have one place to land.
- Cons: Odoo must adapt to EIE's field names rather than its own.

### Option B: Keep an Odoo-facing dialect (`entity_snapshot`, top-level
`entity_id`, `status`, `final_fields`, `writeback`)
- Pros: shorter Odoo mapping code; matches some existing Odoo storage shapes.
- Cons: a second external contract for one action; every EIE change needs a
  translation update on both sides; the dialect was the original source of
  semantic drift. **Rejected.**

## Decision

The only canonical Odoo enrichment protocol is:

```
EnrichRequest → action="converge" → EnrichResponse
```

Odoo produces an EnrichRequest-compatible payload and consumes canonical
EnrichResponse semantics, including `state` and `fields`.

The alternate production wire dialect (`entity_snapshot`, top-level
`entity_id`, `status`, `final_fields`, `writeback`) is **not canonical** and
must not be reintroduced to simplify Odoo integration.

## Consequences

- Internal Odoo compatibility dataclasses may derive convenience attributes
  (for example an internal `status` derived from canonical `state` +
  `failure_reason`) **only** when they are read from the canonical wire and
  never emitted as a second external contract.
- Odoo storage shapes are free to differ from the wire; the wire is not.

## Invariant

```yaml
id: INV-ONE-CONVERGE-CONTRACT
statement: >
  The canonical converge action has one production domain protocol:
  EnrichRequest-compatible request to EnrichResponse-compatible response.
severity: release_blocking
```
