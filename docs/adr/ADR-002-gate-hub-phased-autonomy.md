# ADR-002: Gate Hub, CEG Routing, and Phased Autonomy

**Status:** Accepted  
**Date:** 2026-06-04  
**Deciders:** Igor Beylin  
**Scope:** External intelligence integration (`plasticos_buyer_match_engine`, `plasticos_enrichment`, brokerage pipeline)  
**Related:** [GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md), [ARCHITECTURE.md](../../ARCHITECTURE.md)

## Context

PlasticOS matching and enrichment will move to external engines that are more capable than in-Odoo implementations:

- **[Cognitive.Engine.Graphs](https://github.com/cryptoxdog/Cognitive.Engine.Graphs)** (CEG) — graph-based buyer matching
- **Inference / enrichment engines** — partner and material intelligence

Odoo must remain the ERP spine: intake, offers, transactions, human review, and audit trails. Operators need human-in-the-loop checkpoints while the system is battle-tested.

A draft Gate integration pack (`Current Work - IGNORE/.../Odoo - Gate Integration`) incorrectly routed web-lead triage through Gate and removed local fallback paths. That conflicts with this decision.

## Decision

### 1. Gate is the mandatory hub — never Odoo → CEG direct

All external intelligence calls use the **Constellation Gate** transport pattern:

```
Odoo  ──TransportPacket──►  Gate  ──►  CEG / EIE / workers
Odoo  ◄──TransportPacket──  Gate  ◄──
```

- Odoo imports **`constellation_node_sdk`** only at Gate client seams.
- Odoo **must not** call CEG HTTP endpoints directly (no bypass of Gate).
- EIE and CEG are never imported or invoked from Odoo model code.

### 2. Odoo local engines are fallback — not the primary path

When Gate or downstream nodes are unavailable:

- **Matching:** fall back to in-Odoo Stage-1 Python gates + Neo4j/local matcher (current `plasticos.buyer.matcher` behavior).
- **Enrichment:** fall back to in-Odoo crawl/extract/inference pipeline.
- **Web lead triage:** remains **in Odoo always** in Phase 1 (local LLM/vision/HOT-COLD). No Gate fallback needed because Gate is not on this path yet.

Primary path when Gate is healthy: **Gate → CEG** for matching (and Gate → converge for enrichment when enabled).

### 3. Phased autonomy — humans first, automation later

Human checkpoints stay in place until each step proves reliable in production. Autonomy increases by **phase**, not by deleting audit trails.

| Phase | Summary |
|-------|---------|
| **Phase 1** | Human review on HOT leads, match lines, and Send Offer. Gate for matching (and optional enrichment) only. |
| **Phase 2** | Smarter defaults (e.g. top-N match pre-selection, pre-filled offers). Human still approves Send Offer. |
| **Phase 3** | Gate-routed web-lead triage and higher autonomy — only after Phase 1–2 metrics justify removing middle steps. |

Full phase definitions, graduation criteria, and deferred pack scope: **[GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md)**.

### 4. Brokerage pipeline ownership (Phase 1)

```
Web lead → Odoo (normalize, LLM, vision, HOT/COLD)
         → Human review (HOT)
         → Intake
         → Match to Buyers → Odoo → Gate → CEG → Gate → Odoo
         → Human review match lines + select buyers
         → Offer draft (editable, attachments)
         → Send Offer (explicit human action)
```

Gate does **not** participate in web-lead triage in Phase 1.

## Consequences

### Positive

- Single egress point for compliance, routing, and observability (Gate).
- CEG/inference power without coupling Odoo to multiple HTTP APIs.
- Graceful degradation when nodes fail (local fallback preserved).
- Clear product path from supervised brokerage to higher autonomy.

### Negative / constraints

- Requires `constellation-node-sdk` in Odoo runtime and `plasticos.gate.url` ICP when Gate matching is enabled.
- Gate integration code must implement **try Gate → fallback local**, not replace-and-raise.
- Draft pack items that override `_run_triage_pipeline()` via Gate are **out of scope** until Phase 3.

### Implementation rules (agents)

1. Do **not** apply `web_lead_gate_bridge` or enable `plasticos.gate.webleads_*` in Phase 1.
2. Matcher seam: `find_matches_for_supplier()` — Gate primary, local matcher on failure or when `plasticos.gate.matching_enabled` is off.
3. Preserve `intake_extension.action_match_to_buyers()` as the UI entry point; persist to `plasticos.intake.match` and `plasticos.match.result`.
4. `action_send_offers()` remains human-triggered through Phase 2.
5. Log Gate correlation IDs (`gate_packet_id`, run_id) for match quality auditing.

## References

- External repos: [Cognitive.Engine.Graphs](https://github.com/cryptoxdog/Cognitive.Engine.Graphs), Constellation Gate / `constellation_node_sdk`
- In-repo draft pack (not authoritative; subject to ADR-002): `Current Work - IGNORE/Odoo - Deployment Work/Odoo - Gate Integration/`
- Current matcher seam: `plasticos_buyer_match_engine/models/matcher.py`, `intake_extension.py`
- Web lead triage (Phase 1 local): `plasticos_web_leads/models/web_lead.py`
