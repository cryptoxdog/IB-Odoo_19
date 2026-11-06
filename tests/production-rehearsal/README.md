# Staging → Production Promotion Rehearsal

**Purpose:** Repeatable end-to-end gate that must pass before every promotion of `Staging` into `Production`.

## What it proves

| Gate | Evidence |
|------|----------|
| Staging merges cleanly into Production | `git merge-tree` — zero conflict markers |
| All 53 PlasticOS + Enterprise modules load | `make install-smoke` on the pinned fixture |
| Web lead webhook reaches the wired end (crm.lead) | HOT Cognito POST → intake → crm.lead |
| ERP counterparties, addresses, contacts, roles, salesreps import | `make import-erp LIMIT=10%` |
| VanillaSoft contacts resolve against ERP partners | `make import-vanillasoft` (7-day floor, key from Infisical) |

## Run

```bash
bash tests/production-rehearsal/run.sh
```

Evidence is written to `evidence/YYYY-MM-DD_HHMMSS/` and committed with the kit. `evidence/latest` points at the newest run. Do not put secrets in those files.

## Prerequisites

- Local branch is `Staging` and `HEAD == origin/Staging`
- Docker Compose is up (`docker compose ps` shows `db` healthy)
- The pinned fixture `odoo_test_tpl_ee_c9e8a81f52f23680` is admitted (`bash scripts/test_env.sh status`)

### Credentials (auto-resolved — no manual setup required)

| Secret | Source | How |
|--------|--------|-----|
| `VANILLASOFT_API_KEY` | **Infisical** `cursor-governance` project | `run.sh` binds it via `capability_bind.py` and injects into clone ICP. No `.env.local` entry needed. |

> `run.sh` calls `capability_bind.py --check VANILLASOFT_API_KEY` before Gate 7. If the bind
> returns `source=infisical`, the value is fetched in-process and written directly into the
> `plasticos_crm_sync.vanillasoft_api_key` ICP param of `odoo_test_cutover`. The key is never
> printed, never echoed, and never stored in the kit or evidence.

### ERP source

Gate 6 reads the restored ERP database. A `.bak` is the restore input; the importer does not open it. Restore the backup into SQL Server, then set `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` to that server and database before `run.sh`. The values are not printed. If either is unset, Gate 6 is blocked and VanillaSoft does not start.

The frozen grid under `erp_extracted_data/bulk/` is a regression fixture. Gate 6 fails when the census `payload_kind` is `grid` or `statements`. Only `database` passes.

## Evidence structure

```
evidence/
└── 2026-11-05_144200/           ← one folder per run (UTC timestamp)
    ├── 00-staging-sha.txt        ← git HEAD and origin/Staging SHA
    ├── 01-production-sha.txt     ← git origin/Production SHA
    ├── 02-merge-tree.txt         ← merge-tree output + conflict count
    ├── 03-install-smoke.txt      ← make install-smoke exit code + summary
    ├── 04-weblead-result.json    ← /api/v1/cognito-webhook response
    ├── 05-erp-summary.json       ← ERP import summary (records_seen/created/etc.)
    ├── 06-crm-result.json        ← VanillaSoft 100-contact result
    └── verdict.txt               ← ready | blocked | failed + reason
```

## Repeating safely

`run.sh` **always** reclones `odoo_test_cutover` from the admitted template before any data write. It never rebuilds the template. Each run starts from a clean fixture state.

## Kit files

| File | Role |
|------|------|
| `run.sh` | Full orchestrator — runs all 7 gates in order |
| `payloads/cognito_hot.json` | Proven HOT Cognito webhook body |
| `weblead_e2e.sh` | Web lead e2e helper (called by run.sh) |
| `erp_slice.sh` | ERP 10% slice helper (called by run.sh) |
| `crm_100.py` | Notes that Gate 7 is `make import-vanillasoft`; run.sh does not pipe this file |
| `expected/blockers.yaml` | Named blockers beyond the wired end |
| `evidence/` | Per-run dated evidence subfolders |
