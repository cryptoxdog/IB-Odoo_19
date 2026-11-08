# ADR-015: Persistence Shells for Matching and Enrichment

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** Role of `plasticos_matching` and `plasticos_enrichment` after mothball
**Related:**
[ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md),
[ADR-009-enrichment-selection-ranking-not-in-odoo.md](ADR-009-enrichment-selection-ranking-not-in-odoo.md),
[ADR-010-odoo-consumer-trigger-ownership.md](ADR-010-odoo-consumer-trigger-ownership.md),
[ADR-013-fail-closed-gate-transport.md](ADR-013-fail-closed-gate-transport.md)

## Context

Module names and older READMEs still sound like in-Odoo “engines.” After M4–M8 they are Gate orchestration + persistence + UX shells.

## Decision

### 1. Shell responsibilities (allowed)

| Module | Allowed |
|--------|---------|
| `plasticos_matching` | Trigger Gate `match`; persist runs/results/exclusions; operator retry/audit; intake match lines for human review |
| `plasticos_enrichment` | Trigger Gate `converge`; persist runs/sources/proposals/provenance; allowlisted writeback; operator retry/audit |
| `plasticos_gate` | Sole SDK TransportPacket client |

### 2. Forbidden inside these shells

- Local Neo4j / Stage-1 buyer matcher reintroduction
- Local crawl/extract/YAML inference as intelligence authority
- Enrichment selection/ranking engines duplicating CEG health (ADR-009)
- Silent success when Gate fails (ADR-013)

### 3. Naming / docs

Prefer “Gate orchestrator / result store” language over “matching engine” / “enrichment engine” for Odoo modules in new docs (cleanup tracked in ADR-019).

## Consequences

### Positive

- Agents stop stuffing intelligence into the wrong repo layer.
- Clear test surface: transport mapping, ACL, UX, provenance — not scoring math.

### Negative / constraints

- README/manifest summaries may lag until ADR-019 cleanup.

### Implementation rules (agents)

1. New fields/models in these modules must support persistence, audit, or Gate I/O — not scoring authority.
2. Cross-check M8 `ci/check_no_local_intelligence.py` before adding graph/inference deps.

## References

- Module manifests and orchestrator/run models
- ADR-003-single retirement evidence (M7/M8)
