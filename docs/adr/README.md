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
