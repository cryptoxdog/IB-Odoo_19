# Staging → Production Promotion Rehearsal

**Purpose:** Repeatable end-to-end gate that must pass before every promotion of `Staging` into `Production`. `ready` is evidence for a human decision; the kit never merges, deploys, or writes Production.

## What it proves

| Gate | Evidence |
|------|----------|
| The rehearsal runs exactly the fetched `origin/Staging` | Gate 1: branch, SHA and a clean tree, before any side effect |
| Staging merges cleanly into Production | `git merge-tree --write-tree` exit status |
| All PlasticOS + Enterprise modules load | `make install-smoke` on the pinned fixture (cached fingerprint match is labelled as such) |
| The clone is fresh and empty | `test_env.sh clone/upgrade/assert-clone` + business-partner census (inactive included) |
| Web lead webhook reaches the wired end (crm.lead) | HOT Cognito POST → intake → one unassigned non-Won opportunity, read back from the clone; replay creates nothing |
| ERP counterparties, addresses, contacts, and the 10% native documents | `make import-erp LIMIT=10%`, summary + census + clone layer counts + field-level source comparison |
| VanillaSoft contacts import against ERP partners | `make import-vanillasoft` over a seven-day window, judged by the owner's business acceptance |

## Run

```bash
bash tests/production-rehearsal/run.sh
```

Exit 0 only on `ready`. Evidence is written to `evidence/YYYY-MM-DD_HHMMSS/` and `evidence/latest` points at the newest run once its verdict is written. Run folders are local and git-ignored: they hold runtime logs. Publish a sanitized `verdict.json` deliberately if a run must be recorded. The committed `evidence/2026-11-05_192900/` is historical and is not rewritten.

## Prerequisites

- Local branch is `Staging`, `HEAD == origin/Staging` after a fetch, and the tree is clean (untracked files included)
- Docker Compose is up (`docker compose ps` shows `db` healthy)
- The pinned fixture `odoo_test_tpl_ee_c9e8a81f52f23680` is admitted (`bash scripts/test_env.sh status`)
- Exclusive use of the shared runtime: the Compose project, `odoo_test_cutover`, the rehearsal port (`REHEARSAL_PORT`, default 18069) and container `odoo_rehearsal_<port>`. Gate 5 refuses an existing container or an answering port instead of removing it
- git ≥ 2.38 (`merge-tree --write-tree`), curl ≥ 7.55 (`-H @file`)

### Credentials (auto-resolved — no manual setup required)

| Secret | Source | How |
|--------|--------|-----|
| `VANILLASOFT_API_KEY` | **Infisical** `cursor-governance` project | `run.sh` binds it via `capability_bind.py` and writes it into the clone ICP through psql stdin. Never on argv, never printed, never stored. |
| Web-lead bearer | `plasticos.web.lead.config.api_key` | Read from the clone (or `odoo`, or `ODOO_WEB_LEAD_API_KEY`); docker and curl read it from the environment / a private header file |
| ERP reader password | `~/.l9/erp-proof/reader.pw` | Exported to the import only; never echoed |

Each helper scans the evidence for the credential values it handled; a hit is redacted in place and fails the gate.

### ERP source

Gate 6 calls `make import-erp` on the cutover clone. The importer reads the database that is already restored in container `cie-sql-proof`: `host.docker.internal` port `14330`, login `erp_reader`. The database name is the existing file `~/.l9/erp-proof/database` and the password is `~/.l9/erp-proof/reader.pw`. Neither value is printed, and neither is written into `.env.local`. Each table is loaded by its projection script in `plasticos_partner_import/erp_extracted_data/`. An exported `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` still win over those defaults.

The frozen grid under `erp_extracted_data/bulk/` is a regression fixture. Gate 6 fails when the census `payload_kind` is `grid` or `statements`, and refuses a payload root outright. Only `database` passes. Gate 7 then calls `make import-vanillasoft` on the same clone.

## Evidence structure

```
evidence/
└── 2026-11-06_205618/            ← one folder per run (UTC timestamp), never reused
    ├── gate-1.json … gate-7.json  ← one receipt per gate (state, reason, side effects)
    ├── 00-staging-sha.txt         ← branch, HEAD, origin/Staging, origin/Production, dirty count
    ├── 00-dirty.txt               ← git status of the tree (empty when clean)
    ├── 01-production-sha.txt
    ├── 02-merge-tree.txt          ← merge-tree exit code, tree id, conflicts
    ├── 03-install-smoke.txt       ← make install-smoke output
    ├── 04-clone.log, 04-clone-census.txt
    ├── 04-weblead-*.json          ← receipt, replay, count snapshots, stored chain
    ├── 04-weblead-runtime.log     ← docker/Odoo output (scanned for the bearer)
    ├── 05-erp-summary.json        ← importer summary (the kit never writes into it)
    ├── 05-erp-summary-census.json ← importer census (payload_kind, source_origin)
    ├── 05-erp-layers.json, 05-erp-import.log
    ├── 06-crm-result.json         ← VanillaSoft importer summary
    ├── 06-crm-log.txt, 06-crm-contacts.raw
    ├── 07-remote-refs.txt         ← Staging/Production at start and end
    ├── verdict.json               ← machine verdict
    └── verdict.txt                ← ready | blocked | failed + reasons + per-gate lines
```

## Repeating safely

`run.sh` reclones `odoo_test_cutover` from the admitted template before any data write. It never rebuilds the template, never removes another run's container, and never deletes earlier evidence.

## Kit files

| File | Role |
|------|------|
| `run.sh` | Orchestrator — runs the seven gates in order and always writes a verdict |
| `common.py` | Gate receipts, verdict, evidence scan, and the Gate 5/6/7 proof checks (stdlib) |
| `rehearsal_common.sh` | Shared shell helpers: `rlib`, `db_query`, partner census |
| `weblead_e2e.sh` | Gate 5 helper (called by run.sh) |
| `erp_slice.sh` | Gate 6 helper (called by run.sh) |
| `payloads/cognito_hot.json` | Proven HOT Cognito webhook body |
| `crm_100.py` | Historical note; Gate 7 is `make import-vanillasoft` in run.sh |
| `expected/blockers.yaml` | Blockers that may make a verdict `blocked`, and design-scope notes |
| `test_rehearsal_kit_lib.py` | Every fail-closed branch of the proof checks and the verdict |
| `test_rehearsal_scripts.py` | The real scripts in a throwaway git repo with stubbed make/docker/curl/test_env |
| `test_erp_census_source.py` | Census `payload_kind` and the Gate 6 database source |
| `test_rehearsal_web_lead_receipt.py` | Gate 5 scores `decision` `hot` and `state` `intake_created` |
| `evidence/` | Per-run dated evidence subfolders (local) |

## Kit tests

```bash
python3 -m pytest tests/production-rehearsal -q
```

No Docker, database, HTTP server or credential is used. They prove the kit's
logic, not the application: only a live run on the exact Staging SHA proves `ready`.
