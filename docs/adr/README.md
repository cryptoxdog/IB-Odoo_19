# Architecture Decision Records (ADRs)

**Canonical location:** `docs/adr/` — the only directory for binding PlasticOS architecture decisions.

Former copies under `reports/adr/` were consolidated here (2026-06-04). Do not add new ADRs under `reports/`.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-master-data-field-architecture.md) | Master data field architecture (Many2one registries) | Accepted |
| [ADR-002](ADR-002-gate-hub-phased-autonomy.md) | Gate hub, CEG routing, phased autonomy | Accepted |
| [ADR-002 (nav)](ADR-002-navigation-menu-architecture.md) | Navigation menu architecture | Accepted |
| [ADR-003](ADR-003-contact-import-configuration.md) | Contact import configuration | Accepted |
| [ADR-004](ADR-004-intake-vs-material-profile-domain-split.md) | Intake vs material profile domain split | Accepted |
| [ADR-005](ADR-005-intake-material-profile-delta-bridge.md) | Intake–material profile delta bridge | Accepted |
| [ADR-006](ADR-006-module-installation-and-display.md) | Module installation and dashboard display | Accepted |
| [ADR-007](ADR-007-deployment-architecture.md) | Deployment architecture (Docker vs Odoo.sh) | Accepted |
| [ADR-008](ADR-008-odoo-action-methods.md) | Odoo `action_*` / `ir.actions.act_window` pattern | Accepted |
| [ADR-009](ADR-009-enrichment-selection-ranking-not-in-odoo.md) | Enrichment selection & ranking live outside this repo (CEG health) | Accepted |
| [ADR-010](ADR-010-odoo-consumer-trigger-ownership.md) | Odoo consumer trigger ownership (when to call Gate) | Accepted |
| [ADR-011](ADR-011-intelligence-action-topology.md) | Intelligence action topology (`match` vs `converge`) | Accepted |
| [ADR-012](ADR-012-crm-writeback-allowlist-provenance.md) | CRM writeback allowlist, merge-not-overwrite, provenance | Accepted |
| [ADR-013](ADR-013-fail-closed-gate-transport.md) | Fail-closed Gate transport (no silent local intelligence) | Accepted |
| [ADR-014](ADR-014-domainspec-ssot-gates-scoring-readiness.md) | DomainSpec SSOT for gates, scoring, readiness ranking | Accepted |
| [ADR-015](ADR-015-persistence-shells-matching-enrichment.md) | Persistence shells (`plasticos_matching` / `plasticos_enrichment`) | Accepted |
| [ADR-016](ADR-016-web-lead-triage-boundary.md) | Web-lead triage boundary (Phase 1 local; not enrichment ranking) | Accepted |
| [ADR-017](ADR-017-constellation-enrichment-feedback-channel.md) | Constellation enrichment feedback channel (CEG health → Gate → EIE) | Accepted |
| [ADR-018](ADR-018-human-brokerage-checkpoints.md) | Human brokerage checkpoints (intake → match → offer) | Accepted |
| [ADR-019](ADR-019-documentation-convergence-supersession.md) | Documentation convergence & supersession map | Accepted |
| [ADR-003 (single)](ADR-003-single-external-intelligence-authority.md) | Single external intelligence authority (Gate → CEG/EIE) | Accepted |

## Namespaced ADR packs

| Pack | Scope | Status |
|------|-------|--------|
| [`gate-integration/`](gate-integration/README.md) | Odoo ↔ Gate_SDK ↔ Constellation.Gate ↔ EIE transport and enrichment boundary (ADR-001…ADR-016, namespaced to that directory) | LOCKED |

A pack keeps its own `ADR-0NN` numbering inside its directory. Root ADR numbers
above always mean `docs/adr/ADR-0NN-*.md`.

**Session index (historical):** [PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md](PROPOSED-ADR-BACKLOG-2026-08-architecture-convergence.md) — drafts for ADR-010…019; decisions now live in the Accepted files above (see ADR-019 §4).

## When to write an ADR

- Cross-module contract that agents and humans must not violate
- Irreversible or expensive-to-change schema or integration choice
- Phase-gated external system behavior (see also `docs/GATE_AUTONOMY_ROADMAP.md`)

## How to add an ADR

1. Pick the next `ADR-NNN` (no duplicate numbers; use suffix in filename for related topics, e.g. `ADR-002-navigation-…`).
2. Copy structure from ADR-001: Context → Decision → Consequences → Compliance/References.
3. Add a row to this README and to [ARCHITECTURE.md](../../ARCHITECTURE.md) ADR table.
4. Link from [AGENTS.md](../../AGENTS.md) if agents must load it for a task class.
5. Optional: register in `docs/roadmap/registry.yaml` when the ADR gates phased delivery.

## Related docs

- [ARCHITECTURE.md](../../ARCHITECTURE.md) — system structure and module layers
- [INVARIANTS.md](../../INVARIANTS.md) — CI-enforced rules
- [docs/GATE_AUTONOMY_ROADMAP.md](../GATE_AUTONOMY_ROADMAP.md) — Gate phases (companion to ADR-002)
