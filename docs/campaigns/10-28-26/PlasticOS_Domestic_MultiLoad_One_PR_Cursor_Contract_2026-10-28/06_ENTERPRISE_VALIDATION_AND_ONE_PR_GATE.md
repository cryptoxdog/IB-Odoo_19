# Enterprise validation and single PR gate

**State of this handoff:** contractual obligations only. None of these commands or scenarios has been executed here.

## Gate 0: predecessor and current authority

- Before *any mutation*, confirm the preceding Documents verification/association PR is **merged into `Staging`**. Record PR URL, merge SHA, final affected Documents owner code, tests and accepted BRS status. If it is not merged, stop (`BLOCKED_PREDECESSOR`).
- Make one new feature branch from the new `origin/Staging` SHA, after checking there are no unrelated local changes. `Staging@04bd0594...` is a historical observation, never an acceptable forced execution base.
- Read current `AGENTS.md`, current accepted `INVARIANTS.md`/ADRs, module BRS/AGENTS, current skill contract and `make pr` policy. If `.github` `coding-agent-execution@1` lacks three authentic matching PASS receipts, report binding UNKNOWN and use only the expressly allowed standalone PlasticOS project contract; do not claim canonical L9 projection admission.
- Inspect the installed Odoo Community **and Enterprise** exact model API, module versions and SQL shapes. Enterprise is required for final pass. Do not pretend a Community simulation proves Enterprise readiness.

## Gate 1: baseline and source census

Record `BASE_SHA`, `PREDECESSOR_MERGE_SHA`, git status, Postgres/Enterprise versions, module manifest revisions, existing test results, current model fields and constraints, full affected consumer graph, and dataset ID. Use a protected/owned clone, never a business database.

Required historical datasets: **(A)** admitted EE fixture clone and crafted positive/negative edge cases; **(B)** operator-authorized, protected historical source dataset (full or irrevocably de-identified with faithful cardinality patterns and stable representative references). Capture every non-null old `plasticos_transaction.load_id` and every stored `plasticos_load.transaction_id`, the difference buckets from `04`, plus IDs/counts of claims, documents, freight events, invoices, bills and commissions. If B is unavailable, do not infer success from A: report `HISTORICAL_RECONCILIATION_UNKNOWN` and block publication.

## Gate 2: implementation proof on owner-native tests

Add Odoo ORM TransactionCase/SavepointCase tests under the correct addon test packages and import them in `tests/__init__.py`. Implement all cases in `05_REQUIRED_ACCEPTANCE_MATRIX.json`, with explicit negative assertions. Existing valid tests must remain intact. If another material defect is found outside the permitted surface, record it and request authority instead of silently widening the PR. Do not weaken tests or bypass controls via `sudo()`.

Suggested environment check and test targets after reading **current** Makefile and test fixture config:

```bash
bash scripts/test_env.sh status
bash scripts/test_env.sh template
bash scripts/test_env.sh clone
make test-module m=plasticos_logistics
make test-module m=plasticos_claims
make test-module m=plasticos_documents
make test-module m=plasticos_documents_native
make test-odoo
make install-smoke
python3 -m pytest tests/ -q
python3 scripts/check_module_wiring.py
python3 ci/check_circular_deps.py
python3 ci/check_orphan_model_refs.py
python3 ci/check_odoo19_xml.py
ruff check plasticos_logistics plasticos_claims plasticos_documents plasticos_documents_native
ruff format --check plasticos_logistics plasticos_claims plasticos_documents plasticos_documents_native
pre-commit run --all-files
make pr-check
```

These are *candidate commands*: run only the applicable, supported CLI with correct environment and current DB ownership. In particular, `make test-module` uses a protected clone and enterprise fixture; if unavailable, record UNKNOWN and do not publish. Any new Python source outside the listed modules must be included in current lint checks. `make pr-check` must run against the final committed/consistent state without non-governed bypass.

## Gate 3: versioned data migration and replay

1. On protected EE clone, execute a fresh install that exercises SQL view creation, field registration and pure model init order; assert no fallback view hides tx ownership indefinitely.
2. On pre-upgrade schema/data snapshot, execute the versioned migration and module upgrade using supported `scripts/test_env.sh`/Odoo mechanisms. Use a **source-data before/after census**, including every old association. Retain old identity under no-data-loss compatibility rules.
3. Re-run the identical upgrade/migration and prove zero further changes. Test a deliberately conflicting mapping: fail closed and restore transaction/clone without residual mutation.
4. Reconcile historical claim attribution, document original/evidence IDs, freight observation/event hashes, account.move references, purchase/sale orders, stock.picking IDs, quantities, revenue/cost/commission and existing audit timestamps. No data loss, new dispatch, accounting post, outbound email, fake buyer or fabricated physical record.
5. Verify effective company and user access on both loads, protected post-dispatch reparenting, and existing outbound freight/dispatch state machines.

## Gate 4: evidence and conclusion

A final `PASS` is valid **only** for the exact tested source/fixture state. Required receipts with source IDs but no private record contents:

- `BASELINE_AND_AUTHORITY.json`
- `SOURCE_CONSUMER_DISPOSITION.md`
- `BEFORE_CENSUS.json`
- `MIGRATION_LEDGER.json`
- `UPGRADE_REPLAY_RESULTS.json`
- `FINANCIAL_AND_EVIDENCE_DIFF.json`
- `ACCEPTANCE_RESULTS.json` including all case IDs and actual results
- `TEST_COMMANDS_AND_LOGS.md`
- `FINAL_EXECUTION_RECEIPT.json` with exact validated git SHA/tree, changed-file summary and delivery state

Do not commit raw business database dumps, emails, PDF originals, sensitive company records or secrets; redact/anonymize before adding any receipt to PR. Runtime evidence kept in verified ignored local artifacts may be summarized in PR without exposing confidential contents.

## Gate 5: ONLY one PR through `make pr`

Publication requires: predecessor merged; clean separate feature branch rooted in post-merge `Staging`; all required test/proof gates genuinely PASS (not SKIP/UNKNOWN); no open critical/high in-scope findings; final verified commit/tree matches submitted head; no architecture/policy drift.

Commit only scoped changes, verify diff and no unrelated/new files, then execute:

```bash
make pr
```

Do not execute `make pr-nosmoke`, raw `git push`, `gh pr create`, `make push` or direct GitHub PR writes. One PR, base=`Staging`; do not merge or deploy. After PR publication, review actual CI, lint, CodeRabbit/Sonar/human feedback and keep correcting in-scope defects on the SAME PR through `make pr`. Do not assert 'merge ready' until remote gates have passed at the delivered head. Inability to run real Enterprise or historical reconciliation requires `BLOCKED`, not ceremonial PR publication.
