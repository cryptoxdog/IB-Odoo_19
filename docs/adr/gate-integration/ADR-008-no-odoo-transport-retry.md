# ADR-008: Odoo owns no transport retry layer

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

Retry already exists at three layers: EIE retries providers, Gate has its own
retry behavior, and Gate_SDK owns transport retry. A fourth retry layer in Odoo
multiplies with the others: `n` Odoo attempts × `m` SDK attempts × `k` provider
attempts is an amplification nobody sized, and it arrives at the worst moment —
when the downstream is already failing.

## Options Considered

### Option A: No Odoo transport retry (chosen)
- Pros: retry budgets stay owned by the layers that can size them; a failure
  surfaces to the operator instead of being amplified.
- Cons: a transient blip is visible to the user rather than silently absorbed.

### Option B: Bounded Odoo retry (e.g. 2 attempts with backoff)
- Pros: hides brief transients.
- Cons: multiplies with three existing retry domains; "bounded" retry layers
  are historically the ones that get raised under incident pressure.

## Decision

IB-Odoo_19 adds no automatic Gate transport retry layer. Provider retries
belong to EIE; Gate's retry behavior belongs to Gate; Gate_SDK transport
behavior belongs to Gate_SDK.

A new Odoo execution may occur only according to explicit business semantics,
using the stable operation identity of ADR-006 — that is, an operator or a
business rule deciding to run again, not a transport loop.

## Consequences

- An operator-visible failure state (repo ADR-013 degraded mode) replaces
  silent retry.
- Operator-initiated retry of the same durable run reuses the same logical
  operation identity (ADR-006), so it is a replay rather than a new operation.

## Invariant

```yaml
id: INV-ODOO-NO-TRANSPORT-RETRY
statement: >
  IB-Odoo_19 must not automatically replay a Gate operation at
  the transport layer.
severity: release_blocking
```
