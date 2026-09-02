# ADR-006: One logical operation identity spans replay boundaries

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Transport replay prevention and domain persistence idempotency operate at
different layers and are implemented by different owners (Gate_SDK and EIE
respectively). They must remain separate mechanisms, but when they refer to the
same business operation they must agree on *which* operation that is.

Independently generated values — for example a transport key derived from a
payload digest and a domain key derived from a run id — describe the same
execution with two different names. Nothing downstream can then correlate a
transport replay with the durable run it belongs to.

## Options Considered

### Option A: One logical identity, reused at both boundaries (chosen)
- Pros: transport replay and domain persistence agree on operation identity;
  a retry of one durable run is recognisable as such at every layer; audit can
  join transport records to Odoo run records.
- Cons: a retry of the same run after the source record changed carries the
  same identity, so a deduplicating downstream may serve the earlier answer.
  That is the accepted trade-off, and it is what "same run" is defined to mean
  (see Consequences).

### Option B: Payload-digest transport key, separate domain key
- Pros: a retry after the partner was edited is treated as a materially
  different request and cannot receive a stale answer.
- Cons: two unrelated names for one logical operation; "same operation" ceases
  to be a business fact and becomes a serialization fact — dict ordering or an
  unrelated field edit changes identity. **Rejected**: it makes replay identity
  undecidable from Odoo's own state.

### Option C: Random key per attempt
- Pros: trivially unique.
- Cons: defeats replay prevention entirely.

## Decision

Every durable Odoo enrichment run has one stable logical operation identity,
preferred semantic form:

```
odoo:enrichment:<durable-run-id>
```

Generate this identity **once**. Use that same logical value wherever required
by the EnrichRequest domain idempotency field, the `TransportPacket` header
idempotency field, and Odoo execution audit state.

Transport idempotency and domain persistence idempotency remain **different
mechanisms**. They share a logical identity; they do not become one subsystem.

Required behavior:

| Situation | Operation ID |
|---|---|
| same durable run, retried | same |
| same partner, new enrichment run | different |
| different partner | different |

## Consequences

- Re-running converge on the same durable run is, by definition, the same
  logical operation. An operator who needs a materially new request creates a
  new run — which is the business act that means "ask again".
- Odoo generates the identity; Gate_SDK owns its transport representation; EIE
  owns its durable domain semantics.

## Invariant

```yaml
id: INV-ONE-LOGICAL-OPERATION-ID
statement: >
  One durable Odoo enrichment execution has one stable logical
  operation identity reused consistently across the domain and
  transport replay boundaries.
severity: release_blocking
```
