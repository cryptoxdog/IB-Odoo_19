# ADR-002: Gate Hub, CEG Routing, and Phased Autonomy

**Status:** Accepted
**Date:** 2026-06-04
**Deciders:** Igor Beylin
**Scope:** External intelligence integration (`plasticos_buyer_match_engine`, `plasticos_enrichment`, brokerage pipeline)
**Related:** [GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md), [ARCHITECTURE.md](../../ARCHITECTURE.md)

> **Supersession (2026-08-07):** §2 “Odoo local engines are fallback” is **not** architectural authority. Binding rules: [ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md) (Gate → CEG/EIE only) and [ADR-013-fail-closed-gate-transport.md](ADR-013-fail-closed-gate-transport.md) (no silent local intelligence). Hub topology and phased human checkpoints in this ADR remain binding unless a later ADR amends them. See also ADR-009–019 architecture convergence set.

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

## Amendment 2026-07-19 (Deciders: Igor Beylin)

**Enrichment converge is live, not review-only.** The original Phase-1 stance kept Gate `converge`
review-only with auto-writeback deferred (ROAD-GATE-024, `scope_out`). Per operator decision,
enrichment must be live-activated and testable on sample data, so:

- `plasticos.gate.enrichment_enabled` defaults to **`1`** (converge attempted whenever a Gate URL is set + SDK present).
- `plasticos.gate.auto_writeback` defaults to **`1`**: converge results are applied to the partner immediately, restricted to the **allowlisted** partner fields (`name, website, city, zip, street, street2, email, phone`), **merge-not-overwrite** (blanks only), with a `plasticos.enrichment.provenance` row per write. ROAD-GATE-024 moves to `scope_in` / `complete`.
- Setting `plasticos.gate.auto_writeback=0` restores review-only (proposal stored, `state="review"`, no writes).
- Contract stays **`action="converge"`** (`ConvergeRequest`); EIE must add a matching `converge` handler (see `docs/track_b/03_enrichment_inference_engine.md`).

**Authority model clarification.** The `TransportPacket` schema (Gate_SDK), hub routing / `/v1/execute`
semantics (Constellation.Gate), and worker action/payload contracts (EIE/CEG) are owned by those
constellation repos. Odoo (`plasticos_gate`) is a **consumer that adapts** to them — it does not own
the transport or worker contracts. Odoo owns only *when* to call Gate, *how* it maps results into CRM
records (allowlists, merge-not-overwrite, fallback), and its own audit/UX. Odoo-side wiring guidance:
[`docs/track_b/04_odoo_gate_consumer_wiring.md`](../track_b/04_odoo_gate_consumer_wiring.md).

Unchanged: Gate remains the mandatory hub, local enrichment remains the fallback, and web-lead
triage stays local in Phase 1 (ROAD-GATE-020/023 still deferred).

## References

- External repos: [Constellation.Gate](https://github.com/Quantum-L9/Constellation.Gate) (hub), [Cognitive.Engine.Graphs](https://github.com/Quantum-L9/Cognitive.Engine.Graphs) (CEG), [Enrichment.Inference.Engine](https://github.com/Quantum-L9/Enrichment.Inference.Engine) (EIE), [Gate_SDK](https://github.com/Quantum-L9/Gate_SDK) / `constellation_node_sdk`
- In-repo draft pack (not authoritative; subject to ADR-002): `Current Work - IGNORE/Odoo - Deployment Work/Odoo - Gate Integration/`
- Current matcher seam: `plasticos_buyer_match_engine/models/matcher.py`, `intake_extension.py`
- Web lead triage (Phase 1 local): `plasticos_web_leads/models/web_lead.py`
