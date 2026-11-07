# Staging → Production Promotion Rehearsal — Specification

A `ready` verdict means all seven gates passed, in order, on one fetched
`origin/Staging` SHA, with `origin/Production` and `origin/Staging` unchanged
at the end. It is evidence for a human promotion decision, not the decision.

## Receipts and verdict

Every gate writes exactly one receipt, `gate-<n>.json` (`common.py`,
schema `l9.plasticos.rehearsal.gate.v1`): gate, state, reason code, redacted
detail, evidence files, exit code, whether it had side effects. States:

| State | Meaning |
|-------|---------|
| `PASS` | Every criterion of the gate was evaluated and met |
| `FAIL` | A criterion failed, or could not be evaluated |
| `BLOCKED` | An external prerequisite is missing; nothing was proven |
| `SKIPPED` | Not run because a gate it depends on did not pass |
| `UNKNOWN` | No receipt, or an unreadable one |

`verdict.json` and `verdict.txt` are written atomically on every exit path:
success, gate failure, early refusal, SIGINT/SIGTERM, and an unexpected abort.

| Condition | Verdict |
|-----------|---------|
| All 7 gates `PASS`, no run-level failure | `ready` |
| Every non-PASS gate is `BLOCKED` on an `expected/blockers.yaml` entry with `verdict_effect: blocked` (or `SKIPPED` behind one) | `blocked` |
| Anything else: a `FAIL`, an `UNKNOWN`, an undocumented block, an unexplained skip, a run-level failure | `failed` |

Run-level failures: `origin/Production` or `origin/Staging` moved, the remote
refs could not be re-read, a credential value was found (and redacted) in the
evidence, the run was interrupted or aborted.

Dependencies: Gate 1 and Gate 2 failures stop the run before any side effect
of a later gate. Gate 3 gates 4. Gate 4 gates 5 and 6. Gate 6 gates 7. A gate
behind a failed one is `SKIPPED`, never `PASS`.

## Gate 1 — Revision identity (no side effects before it passes)

- `git fetch origin` of `Staging` and `Production` succeeds (no pull, merge, reset or checkout)
- Current branch is `Staging`
- `HEAD == refs/remotes/origin/Staging` after the fetch
- The worktree is clean, untracked files included. Only the tracked `evidence/latest` pointer, which every run repoints, is exempt; run folders are git-ignored, and committed historical evidence counts
- `origin/Staging` and `origin/Production` SHAs are recorded once and reused by every later gate

A feature branch or worktree can run the kit tests, never a rehearsal that
claims `ready`.

## Gate 2 — Merge-tree (read-only)

- `git merge-tree --write-tree origin/Production origin/Staging` (git ≥ 2.38)
- Exit 0 with a tree id and no conflict marker → `PASS`
- Exit 1 (conflicts) → `FAIL merge-conflict`; any other exit → `FAIL merge-tree-error`
- A nonzero exit is never read as "no conflicts". No real merge is made

## Gate 3 — Install-smoke

- `make install-smoke` exits 0
- When the log shows `install-smoke evidence matches; not upgrading`, the
  receipt reason is `install-smoke-cached-receipt`: a fingerprint match of a
  previous install, not a fresh install

## Gate 4 — Cutover clone

- `bash scripts/test_env.sh clone odoo_test_cutover`, `upgrade`, then `assert-clone` each exit 0, in that order
- Partner census: `SELECT COUNT(*) FROM res_partner WHERE customer_rank > 0 OR supplier_rank > 0` (inactive partners included) returns exactly one integer, and it is `0`
- A failed query, blank output or a non-integer is `FAIL census-unproven`, never zero
- The admitted template is never rebuilt or written

## Gate 5 — Web lead e2e

- Odoo HTTP starts on the rehearsal port (not 8069) on `odoo_test_cutover`,
  in a container this run created. An existing container or an answering port
  fails the gate; nobody else's container is removed
- POST `payloads/cognito_hot.json` to `/api/v1/cognito-webhook`
  - HTTP 200 and JSON `status == "ok"`
  - `decision == "hot"` (the selection value the controller returns)
  - `intake_id` and `web_lead_id` are non-null
  - `state == "intake_created"` (`lead_id` in the body is the web-lead identity string, not a `crm.lead` id)
- Read back from the clone after the POST and after a replay of the same body:
  - the first POST adds exactly one `plasticos.web.lead`, one `plasticos.intake`, one `crm.lead`, and no `res.partner`
  - the replay returns the same `web_lead_id` and changes none of those counts
  - the stored web lead is `intake_created`, links the same intake, has no partner, and has `crm_lead_id`
  - exactly one `crm.lead` has `source_intake_id` = that intake; it is the linked one, `type = opportunity`, active, unassigned (`user_id` empty), no partner, and its stage is not Won
- Do NOT mock `evaluate_economic_opportunity`; a cold decision is a failure

## Execution-path parity (Gates 6 and 7)

Production and the rehearsal run the same `make` target, the same shell
driver piped into `odoo shell`, and the same dispatcher and mappers, at the
same revision. They differ only in the target database, the authorized
permit, the bounded volume, the source credentials, and where the report and
ledger land. Each gate receipt carries `facts.execution_path` naming the
target, driver, dispatcher, source, bounds, database and `release_sha`, and
the gate reads the driver's own trace lines from the import log rather than
trusting the exit code.

| Source | Make target | Driver | Dispatcher | Production | Rehearsal |
|--------|-------------|--------|------------|------------|-----------|
| ERP | `make import-erp` | `plasticos_partner_import/scripts/import_erp_shell.py` | `plasticos.erp.import` (`erp_import_service.py`), extended by the active `plasticos_transaction/models/legacy_erp_import_service.py` for `sale.order` / `purchase.order` / `account.move` | two one-use permits (`erp_partners`, then `erp_commercial`), full volume, `ERP_REQUIRE_EMPTY` guard | no permit, `LIMIT=10%`, `odoo_test_cutover`, same guard |
| VanillaSoft history | `make import-vanillasoft` with `VANILLASOFT_HISTORY_CENSUS` | `plasticos_crm_sync/scripts/import_vanillasoft_shell.py` → `history()` | `SyncOrchestrator.upsert_contact_external_id`, one ContactID at a time, durable `plasticos.crm.external.ref` rows decide | `crm_history` permit after a committed `erp_commercial` phase, the whole cohort, operator ledger | no permit, `VANILLASOFT_HISTORY_MAX_IDS=REHEARSAL_HISTORY_MAX_IDS`, ledger in the evidence folder |

Neither target reaches the retired CSV partner importer
(`partner_import_service.py`, `scripts/run_import.py`), the retired CSV
transaction importer (`transaction_import_service.py`,
`scripts/run_transaction_import.py`, the wizard) or a second mapper; the kit
tests hold that call graph at the candidate revision. `make import-erp`
refuses to start without `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` and refuses a
payload root, so the frozen grid is never a silent source. `make
import-vanillasoft` selects history mode from the census and refuses a call or
contact floor beside it; the rolling window (`VANILLASOFT_CALL_FLOOR`, owned
by `orchestrator.run_full_import` for range reconciliation) is a separately
named mode, never a fallback for a missing census.

## Gate 6 — ERP import (10% slice)

- Refused before any read or write when `ODOO_STAGE=production`, `ERP_PRODUCTION_PERMIT` is set, `ERP_REQUIRE_EMPTY` is not `1`, or a payload root is set
- The source is the restored database already on `cie-sql-proof`: `host.docker.internal`, port `14330`, login `erp_reader`. The database name is `~/.l9/erp-proof/database` and the password is `~/.l9/erp-proof/reader.pw` (not printed). Exported `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` win when both are set. Missing coordinates are `BLOCKED`
- The census before import (Gate 4 query) is exactly `0`
- `make import-erp LIMIT=10%` runs through `scripts/test_env.sh run` on `odoo_test_cutover`; the importer executes the projection scripts in `plasticos_partner_import/erp_extracted_data/`
- The import exits 0
- `05-erp-summary.json` validates against `contracts/schemas/draft/import-run-summary.schema.json` (`scripts/validate_import_summary.py`), `source == "erp"`, `start_time` is not before the run started
- `records_seen == records_created + records_updated + records_unchanged + records_rejected`, `records_seen > 0`, `records_created > 0`, `duplicates == 0`
- `final_status`: `success` passes; `failed` fails; `partial` passes only when the census lists source-attributed `unresolved` rows (table, kind, key) and no run-level error (`reconciliation`, `payables_reconciliation`) — receipt disposition `partial-source-explained`
- The census sibling `<summary>-census.json` has `payload_kind == "database"` and a non-empty `source_origin`. `grid` and `statements` fail the gate
- Read back from the clone: at least 1 counterparty (`legacy_erp_cp_*`), 1 address (`legacy_erp_address_*`), and 1 contact (`legacy_erp_contact_*`) identity on `res.partner`
- The import log (`05-erp-import.log`) holds the driver's own `ERP source: direct database read (...)` line (the SQL source was selected by `import_erp_shell.py`) and a `DATA VERDICT` line (the run was applied). A missing or unreadable log is `FAIL`, never a pass
- The receipt's `facts.execution_path` names target, driver, dispatcher, commercial extension, source, `LIMIT=10%`, database and `release_sha`
- The kit never writes into the importer's summary or census; a failure is the gate receipt

## Gate 7 — VanillaSoft historical cohort (bounded sample)

- Runs only when Gate 6 passed; otherwise `SKIPPED gate6-not-passed`
- Refused before any read or write when `ODOO_STAGE=production`, `VANILLASOFT_PRODUCTION_PERMIT` is set, `VANILLASOFT_CALL_FLOOR` or `VANILLASOFT_CONTACT_FLOOR` is set (`FAIL rolling-floor-refused`: the gate is the historical cohort, never a window), or `VANILLASOFT_HISTORY_CHECKPOINT` is set (`FAIL history-checkpoint-refused`: an operator ledger is never bound to the disposable clone)
- Operator runtime inputs, read from the environment and never generated, substituted or shrunk by the kit: `VANILLASOFT_HISTORY_CENSUS` (the approved 4,876-ContactID `vanillasoft_contact_id,decision` CSV, inside the checkout because that is the odoo container's only bind mount) and `VANILLASOFT_HISTORY_CENSUS_SHA256` (its independently declared digest). Unset is `BLOCKED` (`vanillasoft-history-census-unbound`, `vanillasoft-history-digest-unbound`); unreadable, outside the checkout, or a file whose SHA-256 is not the declared one is `FAIL`
- `REHEARSAL_HISTORY_MAX_IDS` (default `100`) bounds the session; it is a cap on fetched ContactIDs in cohort order, never a selection
- `scripts/test_env.sh run` validates the history form before make starts: the census, its digest and the ledger must be named, a floor beside them and a production permit are refused, and `_MAX_IDS` / `_FAILURE_BUDGET` must be positive integers. A harness refusal is exit 2 and lands as `FAIL vanillasoft-preflight-failed`; nothing runs outside the harness
- `VANILLASOFT_API_KEY` is bound from Infisical and written into the clone ICP through psql stdin. The value is never on argv, never printed, never stored in the kit or the evidence. Unbound is `BLOCKED vanillasoft-key-unbound`; a failed write is `FAIL`
- The clone's `plasticos_crm_sync.cron_crm_sync_all` row is deactivated (the driver refuses an active incremental cron; production takes the same step), and the durable VanillaSoft refs are counted before the run (`06-crm-refs-before.raw`)
- `make import-vanillasoft` runs through `scripts/test_env.sh run` on `odoo_test_cutover` with `VANILLASOFT_HISTORY_CENSUS`, `VANILLASOFT_HISTORY_CENSUS_SHA256`, `VANILLASOFT_HISTORY_CHECKPOINT=<evidence>/06-crm-history.jsonl`, `VANILLASOFT_HISTORY_MAX_IDS` and the container report path; no floor is passed. The Makefile places the census and ledger on the bind mount itself
- Exit 0 alone proves nothing. The gate reads the history driver's report (`06-crm-result.json`), the ledger (`06-crm-history.jsonl`), the log (`06-crm-log.txt`) and the refs after the run (`06-crm-refs-after.raw`):
  - the report has the `historical_cohort.report` shape: `cohort == 4876`, `classes` over `imported / held / duplicate_skipped / genuine_failed`, `by_decision` over `YES / NO / PENDING`, `dispositioned + undispositioned == cohort`, `stopped` in `null / max_ids / auth / budget`, and `census_sha256` equal to the declared digest. A rolling summary (`records_seen`, …) is `FAIL vanillasoft-history-report-shape`
  - `stopped` is `auth` or `budget`, `dispositions_without_a_source_reason > 0`, `imported_with_error_signals > 0`, or `genuine_failed > 0` → `FAIL`
  - the ledger header is a version 1 cohort ledger bound to the declared census, every row is a disposition, and the row count equals `dispositioned` (the ledger is fresh, so the session is exactly what it recorded)
  - the log holds a `VANILLASOFT_HISTORY_AUDIT` `crm_history.admitted` event for `odoo_test_cutover`, the declared census and `permit: false`, and a `HISTORY VERDICT` line; the rolling banner `=== VANILLASOFT IMPORT SUMMARY ===` is `FAIL vanillasoft-rolling-mode-observed`
  - refs landed = after − before; fewer than the report's `imported` count is `FAIL`
  - no fetched id, `imported == 0`, or nothing landed → `BLOCKED vanillasoft-history-sample-no-import`; the cohort order is never changed to manufacture a pass
- `PASS vanillasoft-history-sample-exercised` means only that the authorized sample exercised the production pipeline. The receipt records `max_ids`, `fetched`, `attempted`, `imported`, `held`, `duplicate_skipped`, `genuine_failed`, `undispositioned`, the durable ref counts and `full_cohort_claimed: false`; it never asserts all 4,876 imported, `historical_data_complete`, `LIVE_DELTA_COMPLETENESS` or `FULL_CURRENT_CONTACT_COVERAGE`

## Out of scope

- Partner creation from web lead (deferred — partner deferral is by design)
- Gate/CEG/EIE triage (Phase 3 only)
- Matching, scoring, offer creation (ERP partners needed first)
- Promotion merge itself (human decision after `ready` verdict)
- Full ERP import (100% of transactions) — 10% is sufficient for the rehearsal
- The full 4,876-ContactID history session and its durable operator ledger; the rehearsal samples the cohort
- Mapping fidelity and material-profile cardinality of the imported contacts (a later phase, after command parity)
- Application, importer and SQL Server fixes; the kit only proves

## Kit constraints

- No secrets in any kit file or evidence file. At the end of Gates 5, 6 and the run, the evidence is scanned for the values of the credentials in play (read from the environment by name); a hit is redacted in place and fails the run
- Bearer token for web lead is `plasticos.web.lead.config.api_key`, the same row `web_lead_api.py` compares. A fresh cutover clone copies that field from the `odoo` database, or from `ODOO_WEB_LEAD_API_KEY`, onto its own config row before the POST (docker reads it from the environment, not argv). curl reads the header from a private file. The value is not printed
- ERP credentials come from the existing `~/.l9/erp-proof/reader.pw` at run time and are not echoed. `.env.local` is not where they are stored
- Known gap outside the kit: `make import-erp` passes `ERP_SQL_PASSWORD` to `docker compose run -e NAME=value` (Makefile), so the value is on that docker process's argv. Fixing it belongs to the Makefile owner
- Evidence files and folders are created with mode 0600/0700. `evidence/latest` is repointed by one atomic rename after the verdict
- The template is never rebuilt by this kit
