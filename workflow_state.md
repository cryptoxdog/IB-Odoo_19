# Workflow State — PlasticOS (IB-Odoo_19)

## PHASE

`odoo-intent-1-ingestion` milestone (GMP-129) — implementation complete on
`agent/claude-code/odoo-intent-1-ingestion`; live-DB proofs recorded UNKNOWN
(no local Odoo runtime on this machine).

## Active TODO Plan

| TODO | Status |
|------|--------|
| todo-01 baseline branch + probes | ✅ done (branch from origin/Staging@7572940; PV-04/PV-06 = no runtime / UNKNOWN) |
| todo-02 LegacyErp mapping-status table | ✅ done (mapping_status.py + completeness test) |
| todo-03 shared import-run summary contract | ✅ done (schema + validator + tests) |
| todo-04 make import-legacy-erp | ✅ done (fail-closed preflight boundary verified) |
| todo-05 LegacyErp runtime gate | ✅ shipped (exit 77; live run UNKNOWN) |
| todo-06 CRM stub adapter removal | ✅ done (19.0.1.7.0 + fail-closed migration) |
| todo-07 per-record classification | ✅ done (counters + summary + runbook table) |
| todo-08 make import-vanillasoft | ✅ done (fail-closed preflight boundary verified) |
| todo-09 manual VS CSV path removal | ✅ done (19.0.2.8.0 + action cleanup migration) |
| todo-10 F4/F5 runtime gates | ✅ shipped (live run UNKNOWN) |
| todo-11 v2 schema disposition | ✅ done (recorded, non-blocking) |
| todo-12 CRM adapter roadmap | ✅ done (docs/runbooks/CRM_ADAPTER_ROADMAP.md) |
| todo-13 classification tests | ✅ done (6 tests, 736 passed suite) |
| todo-14 clean replay | ⚠️ UNKNOWN — requires nonproduction Odoo runtime (PV-04 absent) |
| todo-15 docs + GMP report | ✅ done (AGENTS.md, this file, GMP-Report-139) |

## Files in Scope

plasticos_transaction/legacy_erp/**, plasticos_transaction/scripts/,
plasticos_transaction/models/legacy_erp_import_service.py,
plasticos_crm_sync/** (adapters, orchestrator, run model, scripts),
plasticos_partner_import/** (manual CRM-lead import removal), Makefile,
contracts/schemas/draft/, scripts/validate_import_summary.py, tests/,
tests/runtime_gates/, docs/runbooks/, docs/adr/README.md, AGENTS.md.

## Test Status

- Pure-python: **736 passed, 32 skipped** (baseline was 688/32).
- Ruff: clean on all changed files.
- Runtime gates: shipped; **not run** — no local Odoo runtime (`/opt/odoo-venv`
  absent, Docker daemon down). Recorded UNKNOWN, never fabricated.

## Recent Changes

- [2026-09-17] [EXECUTE] Files: plasticos_crm_sync, plasticos_partner_import, tests | Action: GMP-129 ingestion milestone (classification, stub/manual-path removal, canonical commands) | Tests: 736 passed pure tier
- [2026-09-17] [EXECUTE] Files: plasticos_transaction/legacy_erp, Makefile, docs/runbooks | Action: LegacyErp mapping-status + canonical command + runtime gate | Tests: 730 passed pure tier

## Decision Log

- Canonical LegacyErp command named `import-legacy-erp` — the vendor name is
  a banned identifier (BAN001); deviation from the spec's conceptual name
  recorded in docs/runbooks/LEGACY_ERP_IMPORT.md.
- `plasticos.crm.external.ref` remains the single CRM identity authority;
  `vanillasoft_id` is backfill input only.
- Recovered v2 schemas: preserved as evidence, out of the import critical
  path (disposition in docs/runbooks/CRM_ADAPTER_ROADMAP.md).

## Open Questions

- Live-DB reconciliation, repeat-run and clean-replay proofs (U-01, U-02,
  U-04): blocked on a nonproduction Odoo runtime + VanillaSoft credentials.
- U-03 stub-provider connection rows: expected zero; the 19.0.1.7.0
  migration fails closed if any exist.
- U-06 retired transaction_import_service path: documented-retired; removal
  remains a follow-on cleanup.

## Next Steps

1. Start a nonproduction runtime (Docker Desktop or
   `scripts/setup_local_runtime.sh`) and run
   `make runtime-gate g=run_legacy_erp_import.py` and
   `make runtime-gate g=run_f1_f3_full_import.py` to convert UNKNOWNs to
   evidence.
2. Publish the branch via `PR_STACK= PR_REMEDIATE=0 l9 pr` into Staging.

## Recent Sessions

- ✅ 2026-09-17: GMP-129 odoo-intent-1-ingestion — plan-simple-build-v1 DAG
  (PLAN_DOCUMENT + kernels + GMP) executed; 15 todos, 14 landed, live-DB
  proofs UNKNOWN by environment, suite 736/32 green.
