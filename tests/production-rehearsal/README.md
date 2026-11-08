# Staging → Production Promotion Rehearsal

**Purpose:** Repeat the go-live data sync on whatever checkout the kit is run in. `ready` means that sync completed. It is not permission to promote Staging. The kit never merges, deploys, or writes Production.

## What it proves

| Gate | Evidence |
|------|----------|
| This checkout is the code under test | Gate 1 records branch, HEAD, dirty paths and the fetch result. None of those stop the sync |
| Staging and Production merge-tree | `git merge-tree --write-tree` is recorded. A conflict does not stop the sync |
| All PlasticOS + Enterprise modules load | `make install-smoke` on the pinned fixture (cached fingerprint match is labelled as such) |
| The clone is fresh and empty | `test_env.sh clone/upgrade/assert-clone` + business-partner census (inactive included) |
| Web lead webhook reaches the wired end (crm.lead) | HOT Cognito POST → intake → one unassigned non-Won opportunity, read back from the clone; replay creates nothing |
| ERP counterparties, addresses, contacts, and native documents import from the restored database | `make import-erp` with `ERP_LIMIT=10%` (newest worksheets, plus pinned worksheet 58699 when present; partners stay complete), summary + census + driver trace in the log + clone layer counts + native-document completeness + field-level source comparison of that slice |
| VanillaSoft contacts import against ERP partners | `make import-vanillasoft` rolling window on the clone. The driver loads the packaged crosswalk. Durable refs are read back from the clone |

Both import gates run the same `make` target, driver and dispatcher production
runs, at the same revision; the receipt's `execution_path` names them and the
only differences (database, permit, volume, credentials, evidence location).
SPEC.md "Execution-path parity" is the contract.

## Run

```bash
bash tests/production-rehearsal/run.sh
```

Exit 0 only on `ready`. Evidence is written to `evidence/YYYY-MM-DD_HHMMSS/` and `evidence/latest` points at the newest run once its verdict is written. Run folders are local and git-ignored: they hold runtime logs. Publish a sanitized `verdict.json` deliberately if a run must be recorded. The committed `evidence/2026-11-05_192900/` is historical and is not rewritten.

## Prerequisites

- The checkout contains the code to sync. Branch name, dirt, and whether `origin/Staging` moved do not stop the run
- Docker Compose is up (`docker compose ps` shows `db` healthy)
- The pinned fixture `odoo_test_tpl_ee_c9e8a81f52f23680` is admitted (`bash scripts/test_env.sh status`)
- Exclusive use of the shared runtime: the Compose project, `odoo_test_cutover`, the rehearsal port (`REHEARSAL_PORT`, default 18069) and container `odoo_rehearsal_<port>`. Gate 5 refuses an existing container or an answering port instead of removing it
- git ≥ 2.38 (`merge-tree --write-tree`), curl ≥ 7.55 (`-H @file`)
- Gate 7 does not open or hash `plasticos_crm_sync/Vanillasoft-Scrap-Management.csv`. A missing file does not stop the gate
- No `VANILLASOFT_CALL_FLOOR`, `VANILLASOFT_CONTACT_FLOOR`, `VANILLASOFT_HISTORY_CHECKPOINT`, `VANILLASOFT_PRODUCTION_PERMIT`, `ERP_PRODUCTION_PERMIT` or `ODOO_STAGE=production` in the environment: each is a refusal. The gate sets its own floors
- `scripts/test_env.sh run` admits the rolling form of `make import-vanillasoft` (both floors, no census) and the history form (census, digest, ledger, no floor). Gate 7 uses the rolling form

### Credentials (auto-resolved — no manual setup required)

| Secret | Source | How |
|--------|--------|-----|
| `VANILLASOFT_API_KEY` | **Infisical** `cursor-governance` project | `run.sh` binds it via `capability_bind.py` and writes it into the clone ICP through psql stdin. Never on argv, never printed, never stored. |
| Web-lead bearer | `plasticos.web.lead.config.api_key` | Read from the clone (or `odoo`, or `ODOO_WEB_LEAD_API_KEY`); docker and curl read it from the environment / a private header file |
| ERP reader password | `~/.l9/erp-proof/reader.pw` | Exported to the import only; never echoed |

Each helper scans the evidence for the credential values it handled; a hit is redacted in place and fails the gate.

### ERP source

Gate 6 calls `make import-erp` on the cutover clone. The importer reads the database that is already restored in container `cie-sql-proof`: `host.docker.internal` port `14330`, login `erp_reader`. The database name is the existing file `~/.l9/erp-proof/database` and the password is `~/.l9/erp-proof/reader.pw`. Neither value is printed, and neither is written into `.env.local`. Each table is loaded by its projection script in `plasticos_partner_import/erp_extracted_data/`. An exported `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` still win over those defaults.

The frozen grid under `erp_extracted_data/bulk/` is a regression fixture. Gate 6 fails when the census `payload_kind` is `grid` or `statements`, and refuses a payload root outright. Only `database` passes, and the import log must carry the driver's own `ERP source: direct database read` and `DATA VERDICT` lines. `make import-erp` itself now refuses to start without `ERP_SQL_SERVER` and `ERP_SQL_DATABASE`, on every runner.

### VanillaSoft source

Gate 7 calls `make import-vanillasoft` on the same clone in rolling mode. It passes `VANILLASOFT_CONTACT_FLOOR` (30 days) and `VANILLASOFT_CALL_FLOOR` (7 days). It does not pass a census or a digest. The driver (`plasticos_crm_sync/scripts/import_vanillasoft_shell.py`) loads `plasticos_crm_sync/data/approved_contact_crosswalk.csv` unless the ICP key names another file, then `SyncOrchestrator.run_full_import` binds a crosswalk ContactID to the existing ERP person and creates a `crm.lead` for everyone else. History mode stays on the same Make target for an operator who passes a real two-column census. An operator floor in the environment fails the gate.

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
    ├── 05-erp-summary.json        ← copy of the importer summary (the kit does not modify it)
    ├── 05-erp-summary-census.json ← compact census receipt; the full census stays outside the checkout
    ├── 05-erp-fidelity.json       ← FAIL rows, counts, comparison digest, coverage ledger
    ├── 05-erp-identity-ledger.json ← native-document counts and identity digests
    ├── gate-6.json                ← same compact facts; census totals live here
    ├── 05-erp-layers.json, 05-erp-import.log
    ├── 06-crm-result.json         ← history driver report (cohort, classes, by_decision, stopped, census_sha256)
    ├── 06-crm-history.jsonl       ← this run's append-only ledger (header bound to census + database uuid)
    ├── 06-crm-log.txt             ← driver stdout: VANILLASOFT_HISTORY_AUDIT events, HISTORY VERDICT
    ├── 06-crm-refs-before.raw, 06-crm-refs-after.raw, 06-crm-refs.txt
    ├── 06-crm-cron.raw            ← incremental cron deactivated on the clone
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
| `common.py` | Gate receipts, verdict, evidence scan, execution-path facts, and the Gate 5/6/7 proof checks (stdlib; the Gate 7 shape comes from the owner module `historical_cohort.py`) |
| `rehearsal_common.sh` | Shared shell helpers: `rlib`, `db_query`, partner census, VanillaSoft ref census |
| `weblead_e2e.sh` | Gate 5 helper (called by run.sh) |
| `erp_slice.sh` | Gate 6 helper (called by run.sh) |
| `payloads/cognito_hot.json` | Proven HOT Cognito webhook body |
| `crm_100.py` | Historical note; Gate 7 is `make import-vanillasoft` (history mode) in run.sh |
| `expected/blockers.yaml` | Blockers that may make a verdict `blocked`, and design-scope notes |
| `test_rehearsal_kit_lib.py` | Every fail-closed branch of the proof checks and the verdict |
| `test_rehearsal_scripts.py` | The real scripts in a throwaway git repo with stubbed make/docker/curl/test_env, plus the real Makefile import targets against a stub docker (mode selection, forwarding, refusals, legacy-path injection) |
| `test_erp_census_source.py` | Census `payload_kind` and the Gate 6 database source |
| `test_rehearsal_web_lead_receipt.py` | Gate 5 scores `decision` `hot` and `state` `intake_created` |
| `evidence/` | Per-run dated evidence subfolders (local) |

## Kit tests

```bash
python3 -m pytest tests/production-rehearsal -q
```

No Docker, database, HTTP server or credential is used. They prove the kit's
logic, not the application: only a live run on the exact Staging SHA proves `ready`.
