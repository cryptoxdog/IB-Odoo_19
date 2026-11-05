# ADR-009: One caller deadline governs Odoo → Gate execution

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

An Odoo HTTP timeout, a packet `timeout_ms`, and an SDK client timeout are
three separately maintained numbers describing one execution budget. When they
drift, the packet advertises a budget downstream that the caller does not
actually honour — the header promises 30 s while the caller abandons at 10 s,
or the reverse. Neither value is wrong on its own; the pair is incoherent.

## Options Considered

### Option A: One Odoo budget, SDK owns the mechanics (chosen)
- Pros: the advertised budget and the enforced budget cannot diverge because
  they are derived from one validated value; operators configure one number.
- Cons: Odoo cannot express "wait longer for the HTTP call than the packet
  advertises", which is not a behavior this architecture wants.

### Option B: Independent timeouts per mechanism
- Pros: fine-grained tuning.
- Cons: three values that must be kept consistent by convention; the failure is
  silent and only appears under load.

## Decision

The Odoo application owns one bounded caller ceiling of **≤ 30 seconds**. Odoo
supplies that execution policy once; Gate_SDK owns mapping it into transport
mechanisms.

Target system ladder:

| Layer | Budget |
|---|---|
| Odoo caller / Gate transport | ≤ 30 s |
| EIE complete canonical operation | ≤ 25 s |
| response/error reserve | 2 s |
| provider attempt | ≤ 20 s / remaining budget |

Odoo must not independently maintain an HTTP timeout, a packet timeout, a retry
timeout, and a socket timeout as unrelated values.

## Consequences

- An out-of-range configured budget is rejected rather than clamped: an
  operator who configures 120 s has asked for something this architecture
  cannot honour, and silently serving 30 s turns that into configuration
  fiction that only surfaces as an unexplained timeout under load.
- Where the SDK requires the caller to state `timeout_ms` on a pre-built
  packet, it is derived from the same validated budget object, never from a
  second constant.

## Invariant

```yaml
id: INV-ONE-ODOO-DEADLINE
statement: >
  A single Odoo execution budget governs the Gate invocation;
  transport-specific timeout mechanics are delegated to Gate_SDK.
severity: release_blocking
```
