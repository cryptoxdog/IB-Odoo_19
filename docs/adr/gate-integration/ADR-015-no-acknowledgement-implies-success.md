# ADR-015: No acknowledgement may imply unproven downstream success

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

There are three distinct successes in this path — the packet reached Gate, the
domain operation completed, the result was persisted — and each is easy to
mistake for the others. A 200 response carrying a failed canonical state is the
common case where transport success is read as business success.

## Options Considered

### Option A: Fail closed on anything short of canonical success (chosen)
- Pros: a bad enrichment never reaches a customer record; the operator sees a
  degraded state rather than a plausible wrong answer.
- Cons: more visible failures; transient issues surface to users.

### Option B: Treat a well-formed response as success
- Pros: fewer interruptions.
- Cons: silently promotes partial, failed, or malformed results into CRM
  writeback. **Rejected.**

## Decision

Odoo must interpret only successful canonical responses as successful
enrichment operations.

- A transport success does not imply domain success.
- A domain response does not imply persistence success unless EIE's canonical
  contract guarantees it.

Odoo must fail closed on: transport error; invalid response; non-completed
canonical state; malformed fields; missing required identity.

```
packet returned ≠ business operation completed
```

Only the canonical response contract determines business success.

## Consequences

- A non-`completed` canonical state is recorded as a failure with its reason,
  never as an empty successful enrichment.
- Failure detail must be preserved even when the underlying exception
  stringifies to nothing — an unexplained blank reason is not a usable
  operator-visible state.
