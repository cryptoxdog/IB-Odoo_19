# Execute remaining `l9-ecosystem-fix-plan` from IB-Odoo_19

**Status:** ready, **not started.** This PR only registers the remaining
v1.1.0 campaign. It does not bootstrap `pec` or apply mappers.

This directory is the execution-host copy. Trunk is `Staging`.

## Hosts

| Role | Repo | Branch |
|---|---|---|
| Campaign definition (origin) | `Quantum-L9/Cursor-Governance` | PE campaigns overlay |
| Execution (this repo) | `cryptoxdog/IB-Odoo_19` | `origin/Staging` |
| Runtime ledger | `$HOME/.l9/programs/l9-ecosystem-fix-plan` | outside both trees |

Do not execute from a dirty Odoo feature branch.

## When the operator says run

```bash
ODOO_WT="$HOME/.l9/program-worktrees/l9-ecosystem-fix-plan"
PROG="$HOME/.l9/programs/l9-ecosystem-fix-plan"

# Fresh worktree from origin/Staging, then:
pec reconcile --workspace "$PROG" --repository "cryptoxdog/IB-Odoo_19=$ODOO_WT"
```

Bootstrap a **new** Controller workspace from `CAMPAIGN_SOURCE.yaml` v1.1.0.
Do not reuse the 2026-08-05 ledger. L4 local commits only; publish later with
`PR_BASE=origin/campaign/l9-ecosystem-fix-plan PR_REMEDIATE=0 make pr`.

## Remaining READY work

1. **TASK-002** — `plasticos.gate.auto_writeback` seed and default → `0`.
2. **TASK-004** — `payload.get("candidates")` + `resolve_buyer_partner_id()`.
   Reference: `deliverables/ib-odoo_19/reference/plasticos_ceg_match_mapper.py`.
3. **TASK-006** — converge map, no `total_cost_usd` / writeback invention.
   Reference: `deliverables/ib-odoo_19/reference/plasticos_eie_converge_mapper.py`.

**TASK-007** stays blocked until those three land.
