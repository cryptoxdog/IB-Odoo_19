# ADR-011: Intelligence Action Topology (`match` vs `converge`)

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** Gate action routing from Odoo to CEG and EIE
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md),
[ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md),
[`docs/track_b/01_constellation_gate_node.md`](../track_b/01_constellation_gate_node.md),
[`docs/track_b/02_cognitive_engine_graphs.md`](../track_b/02_cognitive_engine_graphs.md),
[`docs/track_b/03_enrichment_inference_engine.md`](../track_b/03_enrichment_inference_engine.md)

## Context

PlasticOS uses one Gate egress (`plasticos_gate`) for multiple intelligence jobs. Without a hard action map, agents invent direct Odoo→CEG/EIE calls or overload one action for both matching and enrichment.

## Decision

### 1. Canonical routing

```
Odoo ──TransportPacket(action=match)──► Gate ──► CEG
Odoo ◄──────────────────────────────── Gate ◄──

Odoo ──TransportPacket(action=converge)──► Gate ──► EIE
Odoo ◄─────────────────────────────────── Gate ◄──
```

| Action | Destination worker | Odoo builder / sender | Odoo result store |
|--------|--------------------|----------------------|-------------------|
| `match` | Cognitive.Engine.Graphs (CEG) | `build_match_request` / `send_match_action` | `plasticos.match.run` / `plasticos.match.result` |
| `converge` | Enrichment.Inference.Engine (EIE) | `build_converge_request` / `send_converge_action` | `plasticos.enrichment.run` (+ partner writeback) |

Action names may be overridden by ICP (`get_matching_action` / `get_enrichment_action`) but must remain Gate-routed and must not point at the wrong worker class.

### 2. Forbidden paths

- Odoo → CEG or EIE HTTP/SDK bypassing Gate
- Second `constellation_node_sdk` import site outside `plasticos_gate`
- Using `match` packets for enrichment or `converge` for buyer ranking

### 3. Worker-to-worker collaboration

If EIE consults CEG (or vice versa) for field determination, that traffic stays **inside the constellation** (hub/worker policy). It is never a second Odoo egress and never an excuse for Odoo to call both workers for one CRM write.

## Consequences

### Positive

- Stable contracts for Track B builders and mappers.
- Clear ownership: CEG scores matches; EIE converges enrichment.

### Negative / constraints

- Schema changes require Gate_SDK pin + Odoo adapter updates (consumer adapts).

### Implementation rules (agents)

1. New intelligence features need a named Gate `action` and a track_b contract note.
2. Do not add “convenience” direct worker clients in Odoo addons.

## References

- `plasticos_gate/services/gate_client.py`, `gate_builders.py`, `gate_mappers.py`
- ADR-002 topology; ADR-003-single authority
