# v2.8 | Re-pin to current Staging and strategic execution plan

Predecessor: v2.7.5 (`EXPORT_BRS/INTEROP/SOURCE_BOUND_CHANGE_LEDGER_v2.7.5.json`, baseline `677d734fd88615d673501d91de88734b7150ff50`).
Re-pin head: `cryptoxdog/IB-Odoo_19` `Staging@d25da3236887c924c8a0164b00c1198f1804a2ea`, 340 commits later.

v2.8 performs the static half of Gate 0 that the v2.7.5 drift rule (`FAIL_CLOSED_RECONCILE_NEW_DIFF`) requires, and adds the plan for building the addon without contaminating Staging. It is additive: no existing file in this pack is changed except the entry pointers in `00_README.md` and `00_ROADMAP_INDEX.md` and the pack `MANIFEST.json` (version, reading path and member hashes; the v2.7.5 values are kept under `v2_7_5_snapshot`), and no BRS, acceptance case, invariant draft or technical contract is altered.

## Added

- `STRATEGIC_EXECUTION_PLAN_v2.8.md`: Gates 0–2, slices S2–S6 on a stacked umbrella branch, merge rule, BRS mirroring and the scaffold checklist.
- `EXPORT_BRS/INTEROP/REPIN_OVERLAY_v2.8.json`: machine-readable re-pin. It supersedes only the v2.7.5 ledger's target, version, migration-path, ADR, invariant-citation and dependent fields, and records old/new blob ids for all 199 ledger paths.
- `EXPORT_BRS/INTEROP/tools/repin_overlay.py`: regenerates the overlay from git objects (`python3 EXPORT_BRS/INTEROP/tools/repin_overlay.py <repo> <pack-path> <revision> <out.json>`). Each slice re-runs it at its fresh base.

## Re-pin results

- All seven planned successor versions were already passed; v2.8 successors are current + 1 (Logistics 19.0.1.14.20, Documents 19.0.2.1.18, Native Documents 19.0.1.2.14, Security Base 19.0.1.2.25, Automation 19.0.2.1.10, Claims 19.0.1.1.7, Commission 19.0.1.4.9).
- Three planned migration folders are occupied by other merged work and are never overwritten; the scripts move to the successor folders.
- ADR-129 is taken; the Export ADR is reserved as ADR-130.
- The constitution is `INVARIANTS.md` v3.0.0. The ledger cites only pack-local POS-INV-26, which stays a campaign gate.
- Logistics dependents are unchanged.
- 83 of 199 paths changed or were removed since v2.7.5 (47 EDIT targets among them) and must be reconciled at the start of their slice.

## Unchanged status

Business scope, the 14 BRS chapters, 120 rules and 120 acceptance cases are preserved; they become `plasticos_export/business_rules/` at S5, mirroring Logistics and Documents. S1-TARGET is still unobserved, the code grant is still not given, and runtime verification is NOT_RUN.
