# ADR-003: Odoo owns domain semantics, not transport semantics

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

"Use the SDK" is not by itself a boundary: a caller can invoke an SDK and still
own transport policy by choosing destinations, deriving timeouts, and
interpreting transport errors. The boundary has to be stated in terms of
responsibility, not in terms of which library is imported.

## Options Considered

### Option A: Responsibility-based layering (chosen)
- Pros: each concern has exactly one authority; violations are detectable by
  asking "who decides this?" rather than "who called what?".
- Cons: requires naming every concern explicitly; some concerns sit near the
  seam and need adjudication (see the authority table below).

### Option B: Import-based layering ("Odoo may use any SDK symbol")
- Pros: simple to state and to lint.
- Cons: permits the exact leak this pack exists to remove — Odoo can own
  transport policy while importing only public SDK symbols.

## Decision

Odoo owns: CRM → domain request mapping; CRM entity identity; business
operation identity; Odoo-specific context; interpretation of the canonical
domain response; Odoo run persistence; review state; allowlisted writeback
policy; merge-not-overwrite behavior; operator-visible failure state.

Gate_SDK owns transport. Constellation.Gate owns routing. EIE owns enrichment
semantics.

```
Odoo ──domain object──▶ Gate_SDK ──transport──▶ Gate ──routing──▶ EIE
```

No layer may silently absorb another layer's authority.

## Consequences

- A change is reviewed against the layer that owns the concern, not the file it
  lands in.
- Where Odoo must still supply a transport value because the SDK requires it,
  that is recorded as an SDK capability gap (ADR-013), not as Odoo authority.
