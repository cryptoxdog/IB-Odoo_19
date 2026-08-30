# ADR-014: DomainSpec as SSOT for Gates, Scoring, and Readiness Ranking

**Status:** Accepted
**Date:** 2026-08-07
**Deciders:** Igor Beylin
**Scope:** Source of truth for match filters/scores and enrichment readiness prioritization
**Related:**
[ADR-009-enrichment-selection-ranking-not-in-odoo.md](ADR-009-enrichment-selection-ranking-not-in-odoo.md),
[ADR-011-intelligence-action-topology.md](ADR-011-intelligence-action-topology.md),
[ADR-017-constellation-enrichment-feedback-channel.md](ADR-017-constellation-enrichment-feedback-channel.md)

## Context

CEG compiles domain YAML into graph gates and scoring. The same DomainSpec drives readiness/gap/ROI enrichment ranking in CEG health. Duplicating gate math or readiness weights in Odoo would fork the domain contract.

## Decision

### 1. DomainSpec is SSOT (external)

For PlasticOS brokerage intelligence:

| Concern | SSOT | Location |
|---------|------|----------|
| Hard filters (gates) | CEG DomainSpec YAML | `Quantum-L9/Cognitive.Engine.Graphs` `domains/` |
| Soft ranking dimensions | CEG DomainSpec scoring | same |
| Enrichment readiness / gap priority / ROI queue | CEG health over DomainSpec | `engine/health/` |
| CRM field registries / snapshots | Odoo master data + builders | IB-Odoo_19 |

### 2. Odoo emits; it does not redefine

Odoo `build_match_request` / `build_converge_request` send **snapshots and queries** (polymer, form, partner fields, etc.). Odoo must not:

- reimplement CEG gate compilers or scoring assemblers,
- host a second DomainSpec that disagrees with CEG,
- invent readiness weights for enrichment selection (ADR-009).

### 3. Contract drift handling

If DomainSpec changes break Odoo payloads, **Odoo adapts** builders/mappers (consumer). Coordinate schema/action changes via Gate_SDK pins across constellation nodes.

## Consequences

### Positive

- One vertical definition for match + enrichment readiness.
- Onboarding graph build and ranking stay aligned.

### Negative / constraints

- Domain changes require CEG deploy + Odoo adapter verification.
- Agents working only in IB-Odoo_19 cannot “fix” match quality by editing Odoo Python scoring.

### Implementation rules (agents)

1. Match-quality bugs → CEG DomainSpec / scoring first; Odoo only if snapshot mapping is wrong.
2. Enrichment priority bugs → CEG health + DomainSpec; not Odoo cron heuristics.

## References

- CEG `domains/`, `engine/gates/`, `engine/scoring/`, `engine/health/`
- Odoo `plasticos_gate/services/gate_builders.py`
