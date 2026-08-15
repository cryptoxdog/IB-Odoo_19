# Campaign: l9-ecosystem-fix-plan (remaining Odoo surface)

Live source is **v1.1.0**. Completed EIE / CEG / Gate / PR #141 work was
removed from the executable campaign. v1.0.0 is archived under
`history/v1.0.0/`.

| Artifact | Purpose |
|---|---|
| `CAMPAIGN_SOURCE.yaml` | Live remaining-only seed (v1.1.0). |
| `source-integrity-receipt.json` | Digest of the live source. |
| `history/v1.0.0/` | Sealed original seed + 2026-08-05 handoff. |
| `AUTH-001-SUPERSESSION.yaml` | Operator cut to remaining surface. |
| `CURRENT_STATE.yaml` | Staging inspection of leftover `plasticos_gate` gaps. |
| `CAMPAIGN_EXECUTION_BINDING.yaml` | PE v2 / L4 landing rules. |
| `EXECUTION_FROM_ODOO.md` | Runbook. Do not follow until the operator says run. |
| `handoff/CAMPAIGN_HANDOFF.md` | Current handoff. |
| `handoff/handoff.json` | Current remaining-only receipt. |
| `deliverables/ib-odoo_19/` | TASK-004 / TASK-006 reference mappers. Not applied. |

## Remaining work

| Task | State | Work |
|---|---|---|
| TASK-002 | READY | Writeback default `"1"` → `"0"` |
| TASK-004 | READY | `results` → `candidates` + `resolve_buyer_partner_id()` |
| TASK-006 | READY | Converge map, no fabricated fields |
| TASK-007 | BLOCKED | Wave-6 after the three READY tasks |

No open Unknowns. TARGET-001 only. Do not mutate EIE, CEG, or Gate.

**Not started** — no `pec` bootstrap, no Odoo mutation in this pass.
