# ADR-016: Web-Lead Triage Boundary (Phase 1 Local; Not Enrichment Ranking)

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** Separation of web-lead HOT/COLD triage from Gate match/enrichment
**Related:**
[ADR-002-gate-hub-phased-autonomy.md](ADR-002-gate-hub-phased-autonomy.md),
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

### 3. Phase 3 only by a later ADR

Moving triage to Gate requires an ADR amendment. Do not “soft enable” via draft packs.

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
- ADR-002 Phase 1–3 table; ADR-018 human checkpoints

## Amendment 2026-11-11 — REVIEW disposition and evidence-grounded qualification

**Status:** Accepted (implementation behind `qualification_mode`; production activation is a separate operator decision)

### Context

Production triage produced many COLD leads and no HOT ones. A keyword reject list, a weight below 10,000 lb, an unknown weight, or a low-confidence model answer was each enough for COLD, and the economic model only commented on a decision that had already been made. A valuable lead with one missing fact was discarded without anyone seeing it.

### Decision

1. **Three outcomes.** `plasticos.web.lead.decision` is HOT, REVIEW, or COLD. `state` tracks processing (`received`, `review_pending`, `intake_created`, `skipped`, `error`). `review_status` is the human disposition only. A new admission defaults to REVIEW until it is classified; `state` keeps an unprocessed or errored lead apart from a completed REVIEW.
2. **One commercial recommender.** The existing economic model (`economic_evaluator.py`, schema `web-lead-economic-assessment/v2`) recommends HOT, REVIEW, or COLD after evidence reconciliation, before any final decision exists. It may cite only the evidence keys the pipeline supplied (`evidence_refs`). Citations to other keys are dropped and recorded.
3. **Deterministic validator.** `classification_engine.derive_final_disposition` decides, in this order: no usable assessment → REVIEW; a hard exclusion (nonplastic-only material in the seller's own words) → COLD; recommended HOT → HOT only when per-load weight is seller-stated or calculated from a seller count, the material is supported, no evidence conflict is open, and evidence is cited; recommended COLD → COLD only when a deterministic negative fact exists (a confident not-plastic or not-commercial text fact, or a seller-stated weight below the cold floor) and the model cites that fact; the model's own suitability judgment is never negative evidence; otherwise REVIEW. The recommendation, the final disposition, and every override reason are stored in `decision_reasons["qualification"]`.
4. **Signals, not vetoes.** Operator reject terms, the economic weight threshold, and the cold floor become risk indicators and advisory signals. Missing facts are not proof of no value.
5. **REVIEW is assigned work.** REVIEW keeps the lead, sets `review_pending` and `clarification_required`, and schedules one activity for the configured reviewer (`hot_intake_reviewer_id`). The reviewer must be able to edit web leads; if none is configured or the configured user cannot edit them, the handoff is recorded as blocked, with the reason, on the lead. REVIEW creates no partner, intake, or opportunity.
6. **One material identity, no invented facts.** Qualification and intake creation read the same polymer: text AI, then a single polymer the seller names, then agreed confident photos. An unknown source type stays empty on the intake; the configured default is no longer written as if it were evidence. **No invented quantity.** An automatic intake needs a real per-load weight. A broker promotes REVIEW to HOT with a rationale and a verified weight; the actor is recorded. `_create_intake` refuses a zero weight.
7. **Recovery.** Re-Run Triage assesses broker corrections recorded on the lead and keeps each beside the submitted value; the submitted packet is never rewritten. A failed assessment on a lead that already has an intake is re-run by an assessment-only retry. That retry writes through a private method, with no context flag able to open the processed-lead guard, and does not re-fetch attachments, recreate records, change the disposition, or alter an approved snapshot. Broker approval still requires an `assessed` record.
8. **Rollout.** `qualification_mode` on the web-lead configuration: `legacy` (HOT/COLD classifier routes, rollback), `shadow` (default: classifier routes, qualification recorded for comparison), and `live` (validated qualification routes). Leads are never reclassified automatically.

### Unchanged

Phase 1 triage stays in Odoo. No Gate, CEG, or EIE call. HOT does not approve, match, create a partner, make an offer, or contact the seller (ADR-018). The HOT intake and opportunity paths stay idempotent.

### Open

- The provider's retry behaviour after an HTTP 200 carrying `state=error` is not established. Webhook response semantics are unchanged. A failed lead now queues recovery work for the reviewer.
- Accuracy against a broker-labelled historical corpus has not been measured. Do not switch production to `live` until a shadow-period comparison has been reviewed.
