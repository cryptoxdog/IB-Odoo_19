# Staging → Production Promotion Rehearsal — Specification

A `ready` verdict means this checkout's sync completed: all seven gates passed,
in order. It is not permission to promote Staging. Branch name, a dirty tree,
a failed fetch, a merge-tree conflict, and a Staging or Production move during
the run are recorded and do not decide the verdict.

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

Run-level failures: a credential value was found (and redacted) in the
evidence, or the run was interrupted or aborted. A remote move is recorded in
`07-remote-refs.txt` and is not a run failure.

Dependencies: Gate 1 stops only when this checkout has no HEAD. Gate 2 records
the merge-tree and does not stop the run. Gate 3 gates 4. Gate 4 gates 5 and
6. Gate 6 gates 7. A gate behind a failed one is `SKIPPED`, never `PASS`.

## Gate 1 — Checkout identity

- Record the branch, HEAD, dirty paths, the fetch result, and the remote SHAs when a fetch succeeds
- A failed fetch, a branch other than `Staging`, HEAD different from `origin/Staging`, and a dirty worktree are recorded. None of them fails the gate or skips later gates
- Only a checkout with no HEAD commit is `FAIL ref-unresolved`
- Only the tracked `evidence/latest` pointer, which every run repoints, is exempt from the dirty list; run folders are git-ignored, and committed historical evidence counts

## Gate 2 — Merge-tree (read-only evidence)

- `git merge-tree --write-tree origin/Production origin/Staging` (git ≥ 2.38) when both SHAs were resolved
- Exit 0 with a tree id and no conflict marker → `PASS merge-clean`
- Exit 1 (conflicts) → `PASS merge-conflict-recorded`; any other exit, or missing remote SHAs → `PASS merge-tree-unproven`
- The result is written to `02-merge-tree.txt`. No real merge is made, and the sync continues

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
same revision. They differ in the target database, the production permit,
the source credentials, and where the report and ledger land. Each gate
receipt carries `facts.execution_path` naming the
target, driver, dispatcher, source, bounds, database and `release_sha`, and
the gate reads the driver's own trace lines from the import log rather than
trusting the exit code.

| Source | Make target | Driver | Dispatcher | Production | Rehearsal |
|--------|-------------|--------|------------|------------|-----------|
| ERP | `make import-erp` | `plasticos_partner_import/scripts/import_erp_shell.py` | `plasticos.erp.import` (`erp_import_service.py`), extended by the active `plasticos_transaction/models/legacy_erp_import_service.py` for `sale.order` / `purchase.order` / `account.move` | two one-use permits (`erp_partners`, then `erp_commercial`), full volume, `ERP_REQUIRE_EMPTY` guard | no permit, no `LIMIT`, `odoo_test_cutover`, same guard |
| VanillaSoft history | `make import-vanillasoft` with the checkout contact file | `plasticos_crm_sync/scripts/import_vanillasoft_shell.py` → `history()` | `SyncOrchestrator.upsert_contact_external_id`, one ContactID at a time, durable `plasticos.crm.external.ref` rows decide | `crm_history` permit after a committed `erp_commercial` phase, the whole file, operator ledger | no permit, no cap unless `REHEARSAL_HISTORY_MAX_IDS` is already set, ledger in the evidence folder |

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

## Gate 6 — ERP import

- Refused before any read or write when `ODOO_STAGE=production`, `ERP_PRODUCTION_PERMIT` is set, `ERP_REQUIRE_EMPTY` is not `1`, or a payload root is set
- The source is the restored database already on `cie-sql-proof`: `host.docker.internal`, port `14330`, login `erp_reader`. The database name is `~/.l9/erp-proof/database` and the password is `~/.l9/erp-proof/reader.pw` (not printed). Exported `ERP_SQL_SERVER` and `ERP_SQL_DATABASE` win when both are set. Missing coordinates are `BLOCKED`
- The census before import (Gate 4 query) is exactly `0`
- `make import-erp` runs through `scripts/test_env.sh run` on `odoo_test_cutover` with no `LIMIT`; an unset limit is the full import. The importer executes the projection scripts in `plasticos_partner_import/erp_extracted_data/`
- The import exits 0
- `05-erp-summary.json` validates against `contracts/schemas/draft/import-run-summary.schema.json` (`scripts/validate_import_summary.py`), `source == "erp"`, `start_time` is not before the run started
- `records_seen == records_created + records_updated + records_unchanged + records_rejected`, `records_seen > 0`, `records_created > 0`, `duplicates == 0`
- `final_status`: `success` passes; `failed` fails; `partial` passes only when every unresolved row is attributed. A compact receipt proves that with `attributed_count == unresolved_count` and `unattributed_count == 0`. A legacy census proves it by listing `unresolved` rows that each have table, kind, and key. A run-level error (`reconciliation`, `payables_reconciliation`) still fails — receipt disposition `partial-source-explained`
- The published census receipt has `payload_kind == "database"` and an origin digest (`origin_sha256`, or a legacy non-empty `source_origin`). `grid` and `statements` fail the gate. The digest is a sha256 of the importer's origin; the raw origin is not published
- Read back from the clone: at least 1 counterparty (`legacy_erp_cp_*`), 1 address (`legacy_erp_address_*`), and 1 contact (`legacy_erp_contact_*`) identity on `res.partner`
- The import log (`05-erp-import.log`) holds the driver's own `ERP source: direct database read (...)` line (the SQL source was selected by `import_erp_shell.py`) and a `DATA VERDICT` line (the run was applied). A missing or unreadable log is `FAIL`, never a pass
- The receipt's `facts.execution_path` names target, driver, dispatcher, commercial extension, source, limit `full`, database and `release_sha`
- After that read-back, compare every imported native record with the restored SQL source. The checker recomputes quantity, unit price, amounts, dates, document identity, and the supported role and Incoterm classifications itself. It does not call the importer's mapping helpers
- The rehearsal report path is an isolated directory outside the git checkout, mounted into the container at `/erp-isolated`. The importer still writes the full census beside that report. The evidence directory receives only an atomic compact census receipt: payload kind, origin digest, grouped census, classified anomaly counts, a per-class sample capped so the file stays under 1000KB, and unresolved attribution counts. The full census is left in the isolated directory. A crash before the rename leaves the evidence directory without the anomaly array and without the unresolved array
- `05-erp-fidelity.json` is the compact comparison receipt: FAIL rows, the compared and failed counts, a comparison digest, and a coverage ledger. The ledger is independent of that digest. It records expected and observed identity counts and digests, missing and duplicate documents, excluded field names and counts, rejected records, and a partition in which every expected identity is compared, rejected, or excluded and those counts sum. A present comparison digest does not pass an identity outside that partition. Pass rows are counted and not stored. The clone snapshot `05-erp-fidelity-odoo.json` is not written into the evidence directory. This change still materializes the clone comparison in memory. Batch-wise comparison with bounded memory per batch is a later plan; current memory consumption is not a demonstrated problem
- `gate-6.json` carries the same compact facts: the coverage matrix, the coverage ledger, the compared and failed denominators, classification counts, every mismatch, the source fingerprint, the tested SHA, and the verification spec. `05-erp-diagnostics.json` is a bounded sample written only when a mismatch, an unresolved row, or an anomaly exists, and it is not part of the receipt. A row is `rejected` when the census left it unresolved, `unmapped` when the writer intentionally stores nothing, and `precision` when the stored quantity and price reproduce the source amount to the cent. Incoterm expected value is `PO.PriceBasis` when that header is set; otherwise each worksheet on the order origin is applied in lexicographic worksheet-number order, and the last mapped or declined `BuySell.PriceBasis` wins. A blank worksheet does not clear a basis already applied
- A `FAIL` row, or a report whose source or clone extract is missing, fails Gate 6 (`erp-fidelity-discrepancy` or `erp-fidelity-unproven`). An empty comparison is not a pass
- A sale order in state `sale` is the transaction compiler confirming the worksheet. `draft` and `sent` remain when that confirmation did not run. A purchase order outside `draft`, `sent`, and `to approve` fails. A customer invoice sums only worksheet lines that resolve one sale-order header. A material bill whose payable matches the signed purchase total stores each purchase line as an absolute amount
- QuickBooks, opening balances, AR/AP aging, ledger reconciliation, posting historical accounting documents, and financial cutover authorization are outside this check. A historical invoice or bill that is not `draft` fails
- Native-document completeness: the field comparison is seeded from the identities on the clone, so a document class the importer never wrote would never enter it. The gate therefore reads the importer's own accounting line in the log (`ERP import finished: {counts}`, the base service's result record with the commercial extension's `transactions` and `transaction_lines` buckets), requires a full-run scope, and reads the compact identity ledger published from the snapshot: realized lines must be present as order lines, realized transactions must be referenced by persisted documents, a run that realized lines must hold at least one order and one line, and a missing or duplicated document identity fails. The snapshot file is removed after that ledger is published and is not evidence. Missing accounting, a partners-only scope, an absent ledger, or fewer documents than realized is `FAIL` (`erp-run-accounting-unobserved`, `erp-run-not-full`, `erp-native-snapshot-unreadable`, `erp-native-documents-none`, `erp-native-class-missing`, `erp-native-documents-missing`, `erp-native-identity-missing`, `erp-native-identity-duplicate`)
- The kit copies the importer's summary and does not modify it. It does not modify the isolated full census. A failure is the gate receipt
- `python3 tests/production-rehearsal/check_compact_acceptance.py` reads the retained full snapshots under `evidence/2026-11-08_124519` and re-reads `odoo_test_cutover`. It does not start an import. It fails closed when either is absent. It checks that the five empty price-basis values stored as incoterm FOB remain detectable, that a completed publish and an interrupted publish leave the three full dumps out of the evidence directory, and that the compact counts agree with those snapshots

## Gate 7 — VanillaSoft history

- Runs only when Gate 6 passed; otherwise `SKIPPED gate6-not-passed`
- Refused before any read or write when `ODOO_STAGE=production`, `VANILLASOFT_PRODUCTION_PERMIT` is set, `VANILLASOFT_CALL_FLOOR` or `VANILLASOFT_CONTACT_FLOOR` is set (`FAIL rolling-floor-refused`: the gate is the historical cohort, never a window), or `VANILLASOFT_HISTORY_CHECKPOINT` is set (`FAIL history-checkpoint-refused`: an operator ledger is never bound to the disposable clone)
- The contact file is `plasticos_crm_sync/Vanillasoft-Scrap-Management.csv` in the checkout. A missing file is `FAIL vanillasoft-history-census-unreadable`. The kit hashes that file at run time because the harness requires the argument, and it stores no digest. An operator census path or digest in the environment is ignored
- `REHEARSAL_HISTORY_MAX_IDS` is passed only when it is already set, and then it must be a positive integer. There is no default cap
- `scripts/test_env.sh run` validates the history form before make starts: the census, its digest and the ledger must be named, a floor beside them and a production permit are refused, and `_MAX_IDS` / `_FAILURE_BUDGET` must be positive integers when present. A harness refusal is exit 2 and lands as `FAIL vanillasoft-preflight-failed`; nothing runs outside the harness
- `VANILLASOFT_API_KEY` is bound from Infisical and written into the clone ICP through psql stdin. The value is never on argv, never printed, never stored in the kit or the evidence. Unbound is `BLOCKED vanillasoft-key-unbound`; a failed write is `FAIL`
- The clone's `plasticos_crm_sync.cron_crm_sync_all` row is deactivated (the driver refuses an active incremental cron; production takes the same step), and the durable VanillaSoft refs are counted before the run (`06-crm-refs-before.raw`)
- `make import-vanillasoft` runs through `scripts/test_env.sh run` on `odoo_test_cutover` with `VANILLASOFT_HISTORY_CENSUS` set to the checkout file, `VANILLASOFT_HISTORY_CENSUS_SHA256` set to that file's hash, `VANILLASOFT_HISTORY_CHECKPOINT=<evidence>/06-crm-history.jsonl`, and the container report path. `VANILLASOFT_HISTORY_MAX_IDS` is included only when `REHEARSAL_HISTORY_MAX_IDS` is set. No floor is passed. The Makefile places the census and ledger on the bind mount itself
- Exit 0 alone proves nothing. The gate reads the history driver's report (`06-crm-result.json`), the ledger (`06-crm-history.jsonl`), the log (`06-crm-log.txt`) and the refs after the run (`06-crm-refs-after.raw`):
  - the report has the `historical_cohort.report` shape: `cohort` is the length of the census the driver was given, `classes` over `imported / held / duplicate_skipped / genuine_failed`, `by_decision` over `YES / NO / PENDING`, `dispositioned + undispositioned == cohort`, `stopped` in `null / max_ids / auth / budget`, and `census_sha256` equal to the file hashed at run time. A rolling summary (`records_seen`, …) is `FAIL vanillasoft-history-report-shape`
  - `stopped` is `auth` or `budget`, `dispositions_without_a_source_reason > 0`, `imported_with_error_signals > 0`, or `genuine_failed > 0` → `FAIL`
  - the ledger header is a version 1 cohort ledger bound to the declared census, every row is a disposition, and the row count equals `dispositioned` (the ledger is fresh, so the session is exactly what it recorded)
  - the log holds a `VANILLASOFT_HISTORY_AUDIT` `crm_history.admitted` event for `odoo_test_cutover`, the declared census and `permit: false`, and a `HISTORY VERDICT` line; the rolling banner `=== VANILLASOFT IMPORT SUMMARY ===` is `FAIL vanillasoft-rolling-mode-observed`
  - refs landed = after − before; fewer than the report's `imported` count is `FAIL`
  - no fetched id, `imported == 0`, or nothing landed → `BLOCKED vanillasoft-history-sample-no-import`; the cohort order is never changed to manufacture a pass
- `PASS vanillasoft-history-sample-exercised` means the checkout file exercised the production pipeline. The receipt records `max_ids` when a cap was set, `fetched`, `attempted`, `imported`, `held`, `duplicate_skipped`, `genuine_failed`, `undispositioned`, and the durable ref counts. Completeness is the driver's own report for the length of the file it was given

## Out of scope

- Partner creation from web lead (deferred — partner deferral is by design)
- Gate/CEG/EIE triage (Phase 3 only)
- Matching, scoring, offer creation (ERP partners needed first)
- Promotion merge itself (human decision after `ready` verdict)
- A second, capped ERP pipeline. Gate 6 is `make import-erp` with no `LIMIT`
- Selecting contacts from a path other than the checkout file. A missing file fails Gate 7
- Mapping fidelity and material-profile cardinality of the imported contacts (a later phase, after command parity)
- Application, importer and SQL Server fixes; the kit only proves

## Kit constraints

- No secrets in any kit file or evidence file. At the end of Gates 5, 6 and the run, the evidence is scanned for the values of the credentials in play (read from the environment by name); a hit is redacted in place and fails the run
- Bearer token for web lead is `plasticos.web.lead.config.api_key`, the same row `web_lead_api.py` compares. A fresh cutover clone copies that field from the `odoo` database, or from `ODOO_WEB_LEAD_API_KEY`, onto its own config row before the POST (docker reads it from the environment, not argv). curl reads the header from a private file. The value is not printed
- ERP credentials come from the existing `~/.l9/erp-proof/reader.pw` at run time and are not echoed. `.env.local` is not where they are stored
- Known gap outside the kit: `make import-erp` passes `ERP_SQL_PASSWORD` to `docker compose run -e NAME=value` (Makefile), so the value is on that docker process's argv. Fixing it belongs to the Makefile owner
- Evidence files and folders are created with mode 0600/0700. `evidence/latest` is repointed by one atomic rename after the verdict
- The template is never rebuilt by this kit
