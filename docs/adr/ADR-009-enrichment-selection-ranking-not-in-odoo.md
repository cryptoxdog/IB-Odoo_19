# ADR-009: Enrichment Selection & Ranking Live Outside This Repo

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** Igor Beylin  
**Scope:** Why IB-Odoo_19 has no “which partners/leads to enrich, in what order” engine  
**Related:**
[ADR-002](ADR-002-gate-hub-phased-autonomy.md),
[ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md),
[GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md),
[`docs/track_b/02_cognitive_engine_graphs.md`](../track_b/02_cognitive_engine_graphs.md),
[`docs/track_b/03_enrichment_inference_engine.md`](../track_b/03_enrichment_inference_engine.md),
[ADR-010](ADR-010-odoo-consumer-trigger-ownership.md)–[ADR-019](ADR-019-documentation-convergence-supersession.md) (architecture convergence set)

## Context

Operators asked whether PlasticOS Odoo (or EIE) decides **which entities to enrich and in what order**, especially during onboarding when CEG builds the graph from a domain spec.

After Gate mothball (M4–M8):

- Local enrichment crawl/inference and the Odoo enrichment cron batch are **retired** (`plasticos_enrichment` cron `active=False`; methods are no-ops).
- Odoo sends per-run `action=converge` via Gate when a consumer triggers `plasticos.enrichment.run`.
- Ranking/selection logic that *feels* like it “should” live next to enrichment actually lives in **Cognitive.Engine.Graphs** (`engine/health/`), not in this repository and not as EIE’s job.

Without an explicit ADR, agents keep looking for (or proposing) an Odoo cron/queue that reimplements CEG readiness/gap/ROI prioritization — a layer violation and a duplicate of constellation code.

## Decision

### 1. This repo does **not** own enrichment selection or ranking

| Concern | Authority | Repo |
|---------|-----------|------|
| Domain gates / scoring dimensions / graph shape | CEG DomainSpec | `Quantum-L9/Cognitive.Engine.Graphs` |
| Readiness score, gap priority, ROI enrichment queue | CEG `engine/health/` | same |
| Execute converge / enrichment passes | EIE | `Quantum-L9/Enrichment.Inference.Engine` |
| Route packets | Gate | `Quantum-L9/Constellation.Gate` |
| When to open a converge request + CRM writeback | Odoo consumer | **this repo** (`plasticos_enrichment` + `plasticos_gate`) |

**IB-Odoo_19 intentionally has no built-in system that:**

- selects which partners/leads to enrich next,
- orders them by readiness / gate gaps / ROI / domain-spec scoring,
- or runs a production nightly enrichment queue ranked against CEG graph health.

That absence is **by architecture**, not an unfinished Odoo feature.

### 2. Why it is not here

1. **ADR-003 authority split** — Matching/enrichment *intelligence* is external. Selection for enrichment is graph/domain intelligence (CEG health), not ERP orchestration.
2. **EIE is an executor** — EIE runs converge jobs as they arrive through Gate. It does not own onboarding lead selection. (EIE may host SCORE/HEALTH *services* in its own repo; those are constellation concerns, not PlasticOS Odoo modules.)
3. **Odoo is a Gate consumer** — Odoo owns *whether/when* to emit a `TransportPacket` for a known partner/run, allowlisted CRM mapping, provenance, and UX. Current trigger: manual/operator `action_execute` / retry (cron retired in M4).
4. **DomainSpec is the ranking SSOT** — CEG readiness/gap/ROI formulas are derived from the same YAML gates and scoring dimensions used to build the graph. Duplicating that in Odoo would fork the domain contract.

### 3. Where the ranking system *does* live (external)

In CEG (not vendored into this repo):

- `engine/health/readiness_scorer.py` — gate/scoring/freshness readiness
- `engine/health/gap_prioritizer.py` — which **fields** to fill first
- `engine/health/enrichment_trigger.py` — ROI recommendation (`enrich_now` / skip)
- `engine/health/nightly_health_scan.py` — ROI-sorted queue (e.g. top 100, cost ceiling)

Constellation follow-through (CEG health → Gate → EIE) is **out of scope for IB-Odoo_19** until a consumer wiring ADR explicitly adopts consuming that queue. Until then, Odoo must not invent a parallel selector.

### 4. What *is* in this repo (and what it is not)

| In-repo artifact | Role |
|------------------|------|
| `plasticos_enrichment` | Persist runs, proposals, provenance; call Gate converge; apply allowlisted writeback |
| `plasticos_enrichment/data/cron.xml` | Historical / disabled — **not** the ranking engine |
| `plasticos_matching` | Persist match runs/results; Gate `match` orchestration |
| `plasticos_gate` | Sole TransportPacket client |

Retired pre-M4 cron criteria (50 stale sources / 30-day cutoff) were an **Odoo-local** batch heuristic. They are **not** the product ranking design and must not be restored as authority.

### 5. Web leads are a different pipeline

`plasticos.web.lead` triage (HOT/COLD) is Odoo-local in Phase 1 and is **not** the enrichment selection queue. Do not conflate “leads” triage with CEG entity enrichment ranking.

## Consequences

### Positive

- Agents stop searching this repo for a missing enrichment scheduler that belongs in CEG.
- Clear split: CEG ranks → (future) Gate routes → EIE executes → Odoo persists CRM.
- Matches ADR-003 consumer role and M4 Gate-only enrichment.

### Negative / constraints

- Until CEG health → EIE (via Gate) is wired and optionally consumed by Odoo, enrichment volume depends on operator/manual or ad-hoc consumer triggers.
- Docs that still say “Odoo always falls back to local enrichment” or “daily enrichment cron selects partners” are **stale** and must be revised (see [ADR complementary backlog](PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md)).

### Implementation rules (agents)

1. Do **not** reintroduce a production enrichment selection cron in Odoo that reimplements CEG readiness/gap/ROI.
2. Do **not** treat EIE as the orchestrator of “who to enrich next.”
3. If product needs ranked batch enrichment: implement/consume it in **CEG health + Gate + EIE**; Odoo only submits converges and maps results.
4. Cite this ADR (full path) when explaining why ranking code is absent from IB-Odoo_19.

## References

- External: [Cognitive.Engine.Graphs](https://github.com/Quantum-L9/Cognitive.Engine.Graphs) `engine/health/`
- External: [Enrichment.Inference.Engine](https://github.com/Quantum-L9/Enrichment.Inference.Engine) (executor; TODO still lists graph→enrich feedback as constellation work)
- In-repo: `plasticos_enrichment/data/cron.xml`, `plasticos_enrichment/models/enrichment_run.py` (`action_cron_enrich_pending` no-op)
- Companion backlog: [PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md](PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md)
