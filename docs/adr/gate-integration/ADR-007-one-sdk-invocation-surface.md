# ADR-007: One SDK invocation surface replaces the Odoo shadow transport

## Status

Accepted — LOCKED

## Date

2026-08-31

## Context

A layered call sequence such as

```
Odoo business caller → Odoo packet builder → Odoo transport wrapper
                     → Gate_SDK packet API → GateClient
```

gives transport policy several Odoo-side places to live. Each intermediate
layer is an opportunity for Odoo to decide something the SDK should decide.

## Options Considered

### Option A: One local Gate invocation boundary (chosen)
- Pros: a single file to audit; transport policy has nowhere to accumulate;
  every consumer (matching, enrichment) shares one surface.
- Cons: that one file becomes load-bearing and must be kept genuinely thin.

### Option B: Per-consumer adapters (one for matching, one for enrichment)
- Pros: each consumer's call is shaped to its own domain.
- Cons: two transport implementations by construction — exactly the split
  ADR-015 of the repo pack and §15 of the execution contract forbid.

## Decision

Odoo exposes one local Gate invocation boundary. Conceptually:

```python
result = gate.execute(
    action="converge",
    payload=request,
    operation_id=run_id,
    timeout_ms=30_000,
)
```

The exact API must be backed by the real Gate_SDK public contract. Do not
invent this API in Odoo if Gate_SDK does not provide it (ADR-013).

A local adapter may only: read Odoo configuration; map configuration into
Gate_SDK configuration; bridge synchronous Odoo code to async SDK code if
required; invoke the SDK; map SDK exceptions into Odoo application errors.

It must not independently perform transport work.

## Consequences

- **Size heuristic:** if the Odoo Gate adapter requires substantial code for
  packet construction, validation, routing, timeout mechanics, retries, hashes,
  signatures, or transport response parsing, the boundary has drifted.
- Where the adapter must still supply transport arguments because the SDK
  requires a pre-built packet, each such line is recorded as an SDK capability
  gap under ADR-013 rather than accepted as Odoo authority.
