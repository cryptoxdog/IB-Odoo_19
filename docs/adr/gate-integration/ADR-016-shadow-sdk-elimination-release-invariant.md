# ADR-016: Shadow-SDK elimination is a release invariant

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

"Shadow SDK eliminated" is a claim that has previously been made about a
codebase that had merely relocated the duplicated logic into a smaller wrapper.
The phrase needs a checklist that a reviewer can evaluate, not a judgement.

## Options Considered

### Option A: Binary checklist, all conditions required (chosen)
- Pros: unambiguous; a partially eliminated shadow reports as partial rather
  than as done.
- Cons: a repository can be very close to compliant and still read `NO_GO`.
  That is intended.

### Option B: Qualitative assessment ("substantially eliminated")
- Pros: reflects genuine progress.
- Cons: every incomplete state can be described as substantial. **Rejected.**

## Decision

Shadow-SDK elimination is complete only if all of the following hold:

```yaml
manual_packet_creation_in_odoo: false
manual_gate_http_in_odoo: false
manual_transport_hashing_in_odoo: false
manual_transport_signing_in_odoo: false
manual_transport_validation_in_odoo: false
manual_hop_management_in_odoo: false
manual_transport_retry_in_odoo: false
manual_transport_timeout_implementation_in_odoo: false
manual_gate_routing_in_odoo: false
duplicate_transport_error_protocol_in_odoo: false
gate_sdk_transport_authority: true
```

If any remain because Gate_SDK does not expose sufficient public capability:

```yaml
shadow_sdk: PARTIALLY_ELIMINATED
sdk_capability: BLOCKED_EXTERNAL_SDK_CAPABILITY
release: NO_GO
```

Do not classify the integration as complete merely because the duplicated logic
has been moved into a smaller wrapper.

## Consequences

- `manual_packet_creation_in_odoo` remaining because Gate_SDK requires callers
  to pre-build packets does not satisfy the close condition. It must be
  reported, with the exact external delta required (ADR-013).
- The verdict vocabulary is fixed: `ELIMINATED` / `PARTIALLY_ELIMINATED` /
  `PRESENT`. There is no "mostly".
