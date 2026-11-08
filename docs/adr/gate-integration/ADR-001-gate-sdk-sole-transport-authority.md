# ADR-001: Gate_SDK is the sole transport authority

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

IB-Odoo_19 accumulated integration code that duplicated portions of the Gate
transport contract. Multiple locations became responsible for packet
construction, timeout propagation, idempotency propagation, Gate destination
handling, transport error interpretation, correlation metadata, SDK
configuration, and transport invocation.

This produced drift between application callers, Odoo wrappers, and the actual
`Quantum-L9/Gate_SDK` contract: the same concern had two implementations that
could disagree without either being obviously wrong.

## Options Considered

### Option A: Gate_SDK is the sole transport authority (chosen)
- Pros: one implementation per concern; wire compatibility is a property of the
  shared dependency rather than of parallel code; Odoo shrinks to domain work.
- Cons: Odoo is blocked whenever the SDK lacks a capability it needs; requires
  discipline to escalate rather than work around (see ADR-013).

### Option B: Odoo keeps a thin local re-implementation of transport
- Pros: Odoo is never blocked by an SDK gap; local changes ship immediately.
- Cons: two authorities for one wire contract; drift is silent and only
  surfaces as production incompatibility. This is the state this ADR exists to
  end.

### Option C: Vendor the SDK source into Odoo
- Pros: full local control; no dependency resolution risk.
- Cons: a fork by another name; every upstream fix must be re-applied by hand;
  the wire contract stops being shared at all.

## Decision

`Quantum-L9/Gate_SDK` is the sole authority for canonical Gate transport
semantics. Gate_SDK owns:

`TransportPacket`; packet construction; transport defaults; transport
validation; transport hashing; transport signing; transport integrity;
Gate-only HTTP transport; packet timeout mechanics; transport correlation,
causation, lineage, and hop mechanics; transport idempotency representation;
response packet validation; transport retry behavior; transport error taxonomy.

IB-Odoo_19 must not independently implement these concerns.

## Consequences

- Odoo transport code shrinks toward configuration and SDK invocation only.
- Any transport functionality Odoo requires that Gate_SDK cannot express is a
  **Gate_SDK capability gap** (ADR-013) — never permission to recreate that
  functionality inside Odoo.
- Production Odoo code must not independently implement: `TransportPacket`
  hashing, packet signing, packet validation, hop construction, lineage
  construction, HTTP calls to `/v1/execute`, Gate retry algorithms, Gate
  transport serialization, or response transport validation.

## Related

- Repo ADR-013 (fail-closed Gate transport) — complementary; this ADR names the
  authority, ADR-013 names the failure posture.
- ADR-007 (one SDK invocation surface), ADR-013 (capability gaps), ADR-016
  (shadow-SDK elimination) in this pack.
