# Where we left off (max ~1 screen)

**Last session:** 2026-08-07
**Repo:** IB-Odoo_19 (local checkout)
**Branch:** `chore/plasticos-skills-root-ssot`

## OPEN TODO (session load)

**Live Gate → CEG/EIE proof is still open.** `docs/track_b/` and `docs/handoffs/` were removed. Read the ADRs, not those briefs.

1. [`docs/adr/ADR-003-single-external-intelligence-authority.md`](../docs/adr/ADR-003-single-external-intelligence-authority.md)
2. [`docs/adr/ADR-011-intelligence-action-topology.md`](../docs/adr/ADR-011-intelligence-action-topology.md)
3. [`docs/adr/ADR-013-fail-closed-gate-transport.md`](../docs/adr/ADR-013-fail-closed-gate-transport.md)
4. [`docs/adr/ADR-016-web-lead-triage-boundary.md`](../docs/adr/ADR-016-web-lead-triage-boundary.md)

Checklist + status: [`memory-bank/tasks.md`](tasks.md) § "OPEN — Track B".

**Known gap:** transport round-trip proven (`LIVE_TRANSPORT_ROUNDTRIP_PASS`); full live integration (`LIVE_INTEGRATION_PASS`) still open. Local engines retired (M7) — fail closed without Gate.

## Recent local commits (this branch)

- `4e9437f` — track legacy ERP extract under `data/legacy_erp_sm_export/`
- `444ccb4` — IDE/rules, L9 skill adapters, `config/odoo.conf`
