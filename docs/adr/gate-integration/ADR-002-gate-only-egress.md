# ADR-002: Odoo uses Gate only

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

`Constellation.Gate` is the routing authority for the canonical execution
plane. If Odoo knew worker endpoints, the constellation would have two routing
planes: Gate's, and an implicit one encoded in Odoo configuration. The second
plane would be invisible to Gate's policy, observability, and topology
controls.

## Options Considered

### Option A: Gate-only egress (chosen)
- Pros: one routing authority; worker topology can change without touching
  Odoo; Gate policy and audit see every canonical call.
- Cons: Gate is on the critical path for every operation; an Odoo capability is
  unavailable until Gate routes it.

### Option B: Odoo may address workers directly as a fallback
- Pros: survives a Gate outage; lower latency for hot paths.
- Cons: creates a second routing plane that bypasses Gate policy entirely; the
  "fallback" becomes load-bearing and permanent; worker URLs become Odoo
  configuration that drifts from real topology.

## Decision

Odoo communicates only with Gate, through Gate_SDK. Odoo must never directly
address EIE or any other worker service.

```
Odoo → Gate_SDK → Constellation.Gate → resolved canonical worker
```

Odoo production code must not contain an EIE URL, hostname, or port; direct
worker HTTP; worker-selection logic; a peer-service routing table; or a
fallback direct-to-worker transport.

## Consequences

- Gate availability is an Odoo dependency, handled by the fail-closed posture
  of repo ADR-013 — degraded mode, never silent local substitution.
- Adding a worker requires no Odoo change.

## Invariant

```yaml
id: INV-ODOO-GATE-ONLY-EGRESS
statement: >
  IB-Odoo_19 may initiate canonical inter-service execution only
  through Gate_SDK to Constellation.Gate.
severity: release_blocking
```
