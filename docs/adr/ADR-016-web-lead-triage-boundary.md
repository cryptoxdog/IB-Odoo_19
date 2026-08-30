# ADR-016: Web-Lead Triage Boundary (Phase 1 Local; Not Enrichment Ranking)

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** Separation of web-lead HOT/COLD triage from Gate match/enrichment
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md),
[GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md),
[ADR-009-enrichment-selection-ranking-not-in-odoo.md](ADR-009-enrichment-selection-ranking-not-in-odoo.md),
[ADR-018-human-brokerage-checkpoints.md](ADR-018-human-brokerage-checkpoints.md)

## Context

Session discussion of “cron / how many leads” conflated (a) retired enrichment partner batches, (b) CEG enrichment ranking, and (c) Cognito web-lead triage. Those are different pipelines.

## Decision

### 1. Phase 1 web-lead path (binding)

```
Cognito/API → plasticos.web.lead create → Odoo LLM/vision/classify (HOT|COLD)
  → HOT: human review → intake (partner deferred)
  → COLD: skipped / review queue
```

- Processing is **per inbound submission** (event-driven), not a ranked enrichment cron.
- Gate does **not** participate in web-lead triage in Phase 1.
- `web_lead_gate_bridge` / Gate webleads ICP remain **out of scope** until Phase 3 roadmap promotion.

### 2. Explicit non-goals

Web-lead triage is **not**:

- CEG health enrichment selection/ranking (ADR-009)
- EIE `converge` partner enrichment
- Buyer `match` scoring

### 3. Phase 3 only by later ADR/roadmap

Moving triage to Gate requires GATE_AUTONOMY_ROADMAP Phase 3 criteria plus an ADR amendment. Do not “soft enable” via draft packs.

## Consequences

### Positive

- Agents stop wiring Gate into `web_lead.py` prematurely.
- Clear vocabulary: “lead triage” ≠ “enrichment ranking.”

### Negative / constraints

- Dual intelligence stacks (local LLM for leads, Gate for match/enrich) until Phase 3.

### Implementation rules (agents)

1. Respect `.cursor/rules/50-plasticos-web-lead-guard.mdc` and write/unlink guards.
2. Do not call `plasticos_gate` from the Phase 1 triage path.
3. Run web-lead tests before/after any `web_lead.py` change.

## References

- `plasticos_web_leads/models/web_lead.py`
- ADR-002 Phase 1–3 table; GATE_AUTONOMY_ROADMAP.md
