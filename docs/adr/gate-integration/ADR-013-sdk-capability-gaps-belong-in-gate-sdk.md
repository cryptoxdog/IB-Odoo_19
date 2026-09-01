# ADR-013: SDK capability gaps belong in Gate_SDK

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

The most dangerous integration pattern in this architecture is:

```
SDK lacks capability → application writes workaround
                     → workaround becomes permanent
                     → SDK and application drift
```

Every step is locally reasonable. The result is the shadow SDK this pack exists
to remove. The workaround is never labelled as debt at the moment it is
written, because at that moment it is simply "the code that makes it work".

## Options Considered

### Option A: Stop at the boundary; fix the SDK (chosen)
- Pros: the capability lands once, in the layer that owns it, for every
  consumer; the gap is visible as a blocker rather than invisible as code.
- Cons: Odoo is blocked on another repository's release cycle; a local
  workaround would have shipped sooner.

### Option B: Implement locally, migrate later
- Pros: unblocks immediately.
- Cons: "later" is not a commitment anyone holds; the local implementation
  acquires callers and tests and becomes the de-facto contract. This is the
  observed failure mode. **Rejected.**

## Decision

If Odoo requires canonical transport behavior that the Gate_SDK public API
cannot express, implementation **stops at the boundary**. The finding is
classified:

```yaml
status: BLOCKED_EXTERNAL_SDK_CAPABILITY
```

The smallest missing capability is then added to Gate_SDK. Only after that
capability is released and proven may Odoo consume it.

Do not hide an SDK deficiency by creating `OdooGateTransport`,
`OdooPacketFactory`, `CanonicalPacketBuilder`, `CustomGateClient`,
`GateProtocolAdapter`, or any equivalent that independently recreates SDK
behavior under a new filename.

## Consequences

- A blocked integration is reported as blocked, with an exact external delta —
  architecture truth outranks local completion.
- Until the SDK ships the capability, the minimum adapter required to reach the
  existing public SDK is permitted, and every line of it that exists solely
  because of the gap must be identified as such.

## Invariant

```yaml
id: INV-NO-SDK-CAPABILITY-SHADOWING
statement: >
  Missing Gate transport capability must be implemented in Gate_SDK,
  not independently recreated inside IB-Odoo_19.
severity: release_blocking
```
