# L9 Ecosystem Fix — Remaining Odoo Surface

**Program:** `l9-ecosystem-fix-plan` v1.1.0 · **Owner (AUTH-001):** Igor Beylin
**Current authority:** `AUTH-001-L9-ECOSYSTEM-REMAINING-2026-08-14`
**Archived:** v1.0.0 under `history/v1.0.0/` (EIE / CEG / Gate / PR #141 closed there)
**Execution host:** `cryptoxdog/IB-Odoo_19` @ `origin/Staging`
**Recommended terminal verdict:** **INCONCLUSIVE** — prepared, not executed

This pass does **not** run `pec` and does **not** mutate Odoo.

## Live controller state

| | |
|---|---|
| TASK-002 | **READY** — writeback default to review-only |
| TASK-004 | **READY** — candidates + DEC-001 resolver |
| TASK-006 | **READY** — converge map, no fabricated fields |
| TASK-007 | **BLOCKED** on 002 + 004 + 006 |
| GATE-002 / 004 / 005 | **UNKNOWN** until those tasks run |
| GATE-006 | **UNKNOWN** |
| Unknowns | **none** |
| DEC-001 | **accepted → OPTION-B** (locked input) |

Removed from the live campaign: TASK-001, TASK-003, TASK-005, GATE-001,
GATE-003, and all EIE / CEG / Gate / Gate_SDK targets.

## Residual risks

- **RISK-001** — wrong buyer if TASK-004 skips `resolve_buyer_partner_id()`.
- **RISK-003** — quarantine overlap before TASK-007 closeout.

## Not requested in this pass

Bootstrap + reconcile + execute the three READY tasks only when the operator
says run. See `EXECUTION_FROM_ODOO.md`.
