# ADR-017: Constellation Enrichment Feedback Channel (CEG Health → Gate → EIE)

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** Igor Beylin  
**Scope:** Where ranked enrichment queues and graph→enrich feedback belong  
**Related:**
[ADR-009-enrichment-selection-ranking-not-in-odoo.md](ADR-009-enrichment-selection-ranking-not-in-odoo.md),
[ADR-010-odoo-consumer-trigger-ownership.md](ADR-010-odoo-consumer-trigger-ownership.md),
[ADR-011-intelligence-action-topology.md](ADR-011-intelligence-action-topology.md),
[ADR-014-domainspec-ssot-gates-scoring-readiness.md](ADR-014-domainspec-ssot-gates-scoring-readiness.md)

## Context

CEG implements readiness scoring, gap prioritization, ROI triggers, and nightly enrichment queues. EIE TODOs still list graph→enrich feedback. None of that selector lives in IB-Odoo_19 (ADR-009). Product still needs a place to own the **channel**.

## Decision

### 1. Feedback channel ownership (constellation)

```
CEG engine/health (rank entities/fields)
    → Gate (route / envelope)
    → EIE (execute converge)
    → [optional] Odoo consumer maps CRM if Odoo initiated or adopts queue consumption
```

| Layer | Owns |
|-------|------|
| CEG health | Who/what to enrich; ROI/order; DomainSpec-based readiness |
| Gate | Transport and routing |
| EIE | Execute enrichment/converge semantics |
| IB-Odoo_19 | Must **not** host the selector; may later **consume** queue outputs by emitting converges (ADR-010) |

### 2. Acceptance criteria live outside this repo

Wiring completeness (entity loaders, actual Gate dispatch from `trigger_reenrichment_v2`, EIE feedback handlers) is validated in CEG/EIE/Gate repos. This ADR only forbids Odoo from becoming a parallel ranker.

### 3. Optional future Odoo consumer

If PlasticOS adopts batch enrichment from CEG queues, Odoo remains a **client**: receive/list work items → `build_converge_request` → Gate. That adoption needs a small follow-up ADR or amendment with ICP flags — not a silent cron that reimplements CEG math.

## Consequences

### Positive

- Clear home for “nightly top-100 enrichment queue” work.
- Protects ADR-009 boundary while allowing constellation completion.

### Negative / constraints

- Ranked batch enrichment may be incomplete until CEG/EIE finish the channel — visible as manual Odoo triggers today.

### Implementation rules (agents)

1. Do not vendor CEG `engine/health/` into IB-Odoo_19.
2. Do not treat EIE SCORE/HEALTH modules as permission to schedule from Odoo without ADR-010.
3. Document any new Odoo queue-consumer seam in track_b + ICP.

## References

- CEG `engine/health/nightly_health_scan.py`, `enrichment_trigger.py`
- EIE TODO: graph→enrichment feedback channel
- ADR-009
