# ADR-019: Documentation Convergence and Supersession Map

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** Igor Beylin  
**Scope:** Which docs are authoritative after Gate/CEG/EIE architecture convergence; what to revise  
**Related:**
[ADR-003-single-external-intelligence-authority.md](ADR-003-single-external-intelligence-authority.md),
[ADR-009-enrichment-selection-ranking-not-in-odoo.md](ADR-009-enrichment-selection-ranking-not-in-odoo.md),
[ADR-013-fail-closed-gate-transport.md](ADR-013-fail-closed-gate-transport.md),
[PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md](PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md) (historical backlog; ADRs now Accepted)

## Context

Architecture has converged on Gate-mediated external intelligence and Odoo-as-consumer. Many repo files still describe local engines, silent fallback, or Odoo-owned enrichment ranking. Agents follow the nearest doc; contradictions cause wrong implementations.

## Decision

### 1. Authority stack (intelligence / Gate)

When docs conflict, prefer in this order:

1. **ADR-003-single** — intelligence authority  
2. **ADR-009 … ADR-018** — ownership, topology, writeback, fail-closed, DomainSpec, shells, leads, feedback, humans  
3. **ADR-002** — hub topology + phased autonomy (**§2 fallback-as-authority superseded**; see banner)  
4. `docs/GATE_AUTONOMY_ROADMAP.md` — phase criteria  
5. `docs/track_b/*` — consumer/worker wiring (must match ADRs; fix if stale)  
6. `ARCHITECTURE.md`, `AGENTS.md`, `CLAUDE.md` — narrative indexes (must be updated to match ADRs)

### 2. Supersession / refresh map

| Artifact | Disposition |
|----------|-------------|
| `ARCHITECTURE.md` | Refresh Gate/matching/enrichment to ADR-003 + ADR-009–015; remove local-engine authority |
| `AGENTS.md` / `CLAUDE.md` | Load ADR-003-single + ADR-009–013 for intelligence tasks |
| `docs/track_b/00_AGENT_HANDOFF.md` | Fail-closed language (done); keep aligned with ADR-013 |
| `docs/track_b/02` / `03` | No local-fallback acceptance; ADR-009 ranking pointer (done); drop leftover fallback criteria |
| `ADR-002` | Banner: §2 superseded by ADR-003-single + ADR-013 |
| Module READMEs (`plasticos_matching`, `plasticos_enrichment`) | Retitle to Gate orchestrator / result store (ADR-015) |
| Pre-mothball prompts under `Current Work - IGNORE/` | Non-authoritative; do not apply Phase-3 Gate triage |

### 3. Numeric ADR-003 collision

`ADR-003-contact-import-configuration.md` and `ADR-003-single-external-intelligence-authority.md` remain **both Accepted**. Always cite **full filename**. Renumbering is out of scope unless a dedicated ADR is approved.

### 4. Backlog file status

`PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md` becomes a **historical index** pointing at Accepted ADR-010…019; it is not a second source of conflicting decisions.

## Consequences

### Positive

- Single convergence map for agents and humans.
- Explicit stale list reduces reintroduction of local intelligence docs.

### Negative / constraints

- Narrative files (`ARCHITECTURE.md`, READMEs) still need mechanical edits over time; this ADR authorizes that cleanup without new design debate.

### Implementation rules (agents)

1. Before teaching fallback/cron/ranking behavior, check ADR-009/013/015.
2. When editing listed artifacts, remove superseded claims in the same change when practical.
3. Do not treat ignored draft packs as ADR-equivalent.

## References

- ADR-002, ADR-003-single, ADR-009–018
- `docs/adr/README.md` index
