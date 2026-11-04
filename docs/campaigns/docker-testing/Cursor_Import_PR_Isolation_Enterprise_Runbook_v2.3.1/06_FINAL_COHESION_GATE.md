## v2.4.0 combined pre-merge run

BOTH is part of this campaign. Build it locally with `git merge-tree` from M301 and M303, check it out detached, and test it before the operator merges either PR. Do not push that commit and do not resolve conflicts. A conflict is the remediation finding.

PR #303 contains `plasticos_logistics` and other product changes, so BOTH contains them too. Report that. Do not run logistics tests. 'No logistics tests' does not mean 'no logistics changes'. Do not describe BOTH as an import-only branch.

A single fresh Enterprise clone with one combined import-addon module test command proves registry-level compatibility only. Real same-database ERP -> VanillaSoft -> identical replay requires a **separate explicit operator authorization** specifying safe source, data bounds, credentials, owned clone, and the existing permitted importer/replay path. With that missing, record `COMBINED_RUNTIME_PASS; COHESION_NOT_PROVEN` (if applicable), never `COHESION_PASS`. No new fixtures, ad hoc test code, silent `ERP_REQUIRE_EMPTY=0`, imports from live providers, or money/stock event manipulation.

# 06. Final phase I: whole-system CRM + ERP import cohesion

**Status:** RUN IN THIS CAMPAIGN, after M301 and M303 are checked out. This is the pre-merge combined tree, not a post-remediation phase.

**Purpose:** Once all in-scope individual PR behaviors pass at their final approved revisions, verify that the **same combined code** also works as a cohesive ERP and CRM import system. A PR-by-PR green ledger is necessary but insufficient. This phase is about integration interactions, not a new implementation campaign.

## I0. Entry gate: all five conditions are mandatory

1. **Approved fixes only.** Every in-scope PR has a final operator-approved disposition. No unresolved `FAIL`, `BLOCKED`, material `NOT_PROVEN`, or unapproved remediation concerning a required behavior remains. Approved exceptions are named explicitly, with their consequences, and are not converted to PASS.
2. **Final heads independently retested.** All required PR behaviors have individual Enterprise-fixture receipts on the **final code revisions after fixes**. A fix that changes a PR's head invalidates the earlier receipt for that behavior. The independent baseline and evidence IDs in `02_PR_BEHAVIOR_MATRIX.md` remain traceable.
3. **The combined tree is a clean local merge.** `git merge-tree --write-tree` of the M301 commit and the M303 commit exits 0. Record that commit and its tree. Cursor creates this test commit locally and does not push, rebase onto a published branch, or resolve conflicts. A conflict is `BLOCKED_MERGE_CONFLICT` and is itself the finding.
4. **The integration source is auditable and in scope.** Record precisely which independently accepted PR changes and approved fixes the integration tree includes. Check parentage/merge metadata and relevant implementation/test content; squash merges require explicit mapping, not a false ancestry test. If an accepted fix is missing, or an unapproved edit has been added: `BLOCKED_INTEGRATION_CONTENT`, stop. PR #303 is a broad PR containing logistics and other product changes: Cursor may neither transplant a subset nor silently import its entire patch. If a non-logistics successor is needed, the operator must first approve and provide it. PR #303 currently includes a docs-only evidence handoff at `190c497...`, not resolved production/test dispositions; it cannot be admitted as merge-ready by documentation alone. If logistics code is already present as a dependency on an authorized `Staging` revision, **do not test or modify its functionality**.
5. **Same admitted Enterprise fixture.** Reapply `01_SOURCE_AND_FIXTURE_ADMISSION.md` to the clean detached BOTH worktree. The already-existing canonical Enterprise template, its fingerprint, local Docker image, Odoo modules and Postgres service must be verified before creating any clone. No fixture creation, adoption, rebuild, re-stamp, Community fallback, service repair, package installation or unscoped Odoo test run. If any precondition cannot be proven: `BLOCKED`, stop.

**Authority:** Adding this future phase to the plan does not authorize combining PRs or starting a real ERP SQL Server or VanillaSoft import. Source credentials and applied-import permission are a separate operator decision. No source changes or self-healing at any point.

## I1. Prove integration source identity, then choose cheap discriminating probes

Use an approved integration ref supplied at the time of the run. From the original repository, fetch that exact ref and create a new detached worktree, e.g. `../IB-Odoo_19_verify_integration_<runid>`; refuse an occupied path. Verify `git rev-parse HEAD` exactly equals the operator-approved 40-hex SHA, the tree is clean, and Compose `/mnt/extra-addons` maps to this new worktree. The same Enterprise checkout must be mounted at `/mnt/enterprise`.

Record the integration manifest in the evidence folder:

| Required coordinate | Evidence |
|---|---|
| Approved combined SHA/ref, operator approval | 40-hex SHA + exact approved reference |
| Required PR final SHA(s) / merged equivalent | PR number, accepted head, integration relationship |
| Explicitly included approved fixes | Changed files and linked operator decisions |
| Excluded/deferred changes | No unapproved PR content admitted |
| Source digest, Odoo image, existing fixture | Read-only digests / template fingerprint |
| Git status and Compose bind mount | Before-and-after proof |

If the resulting tree does not include **both** the final import/accounting behavior and the approved CRM/ERP contact/history/material behavior, do not label it a whole-system test. Logistics modules installed as preexisting dependencies are not integration scope.

Run the minimal **pure-Python cross-boundary smoke** against this **one integration SHA**. Use the installed test files that actually exist on the integrated tree; do not add or change them. Suggested initial suite:

```bash
python3 -m pytest -q \
  tests/test_erp_source_layer.py \
  tests/test_erp_mapping_status.py \
  tests/test_erp_native_orders.py \
  tests/test_erp_native_document_guard.py \
  tests/test_erp_summary.py \
  tests/test_erp_import_contract.py \
  tests/test_crm_approved_identity.py \
  tests/test_crm_history_links.py \
  tests/test_crm_sync_full_import.py \
  tests/test_crm_sync_completeness.py \
  tests/test_vanillasoft_owner_crosswalk.py
```

Check that each claimed method was **collected and executed**. If a file moved or is absent in the approved tree, record `TEST_DISCOVERY_GAP` with its new owner; do **not** rename paths or patch the test runner. Avoid broad `pytest tests/` as the first diagnostic step, since it dilutes the signal.

## I2. Run import-related addon tests **together**, on ONE fresh Enterprise clone

Once I1 passes, run the **existing guarded test runner** from the approved integration worktree. Confirm the named clone is **absent** and the admitted pinned Enterprise template is already `ready`. The runner supports a comma-separated addon scope; this is one test invocation against a single disposable database:

```bash
# In the operator-approved integrated worktree after repeating document 07 preflight.
INTEGRATED_DB="odoo_test_integrated_$(date -u +%m%d%H%M%S)"
test -z "$(docker exec "$DB_CID" psql -X -U "${POSTGRES_USER:-odoo}" -d postgres -qtA -v ON_ERROR_STOP=1 -c "SELECT datname FROM pg_database WHERE datname='$INTEGRATED_DB';")" || { echo 'STOP: clone exists'; exit 2; }
make test-module \
  m=plasticos_base,plasticos_material_profile,plasticos_partner_import,plasticos_crm_bridge,plasticos_crm_sync,plasticos_transaction,plasticos_documents \
  ODOO_TEST_DB="$INTEGRATED_DB"
```

Use the actual generated `INTEGRATED_DB` only if the read-only absence check confirms it does not exist. Never replace an existing clone. If an addon is not part of the admitted module roster for that exact approved SHA, stop and report `BLOCKED_SCOPE`, not an improvised override. The run upgrades the declared PlasticOS modules only **on the clone**, while restricting test selection to the named import-facing addons. **Never** run `make test-odoo`, logistics tags, Linda tests, claims/offer/matching suites, or unscoped all-addons tests. Existing unrelated dependencies may be loaded by Odoo but are not target features.

Preserve the module `.test-receipt.json` and `.test.log` and classify **every required behavior** in `02_PR_BEHAVIOR_MATRIX.md` by test method, not aggregate count. A method not demonstrably run is `NOT_PROVEN`. Verify joint registry installation, native model availability, owner crosswalk, contact aliases, material/profile uniqueness, call-history owner, transaction reconstruction, header due dates, and the absence of fabricated stock events, postings, payments or settlement as far as these tests actually assert.

After copying evidence outside the source worktree, retire **only this clone** with `bash scripts/test_env.sh drop <exact_db_name>` and record successful retirement. Do not recycle an individual-PR clone.

**Proof limit:** Odoo's module tests often roll back their own transactions. Even a successful single-clone multi-addon run proves that the **combined code and registered assertions are compatible**, not that an ERP import followed by a VanillaSoft import persists and replays correctly on one shared business record graph.

## I3. Combined CRM runtime gate on the **same integration SHA**, with its own guarded clone

If I2 is clean and the approved integration SHA is unchanged, run the preexisting synthetic `make runtime-gate-f1`, followed by `make runtime-gate-f1-accept`. Its F1-F3 receipt must name that **integration SHA** and prove clone retirement. This checks real ORM/PostgreSQL commits, watermarks and archive/restore semantics; it is **not a live VanillaSoft import** and does **not** prove a combined ERP+CRM dataset because it uses a separate owned clone.

If the combined code causes F1-F3 to fail while individual PRs passed, report an `INTEGRATION_REGRESSION` with the first failing boundary. Do not repair or alter test fixtures.

## I4. True same-database end-to-end integration and replay: separate authorization

This is the discriminating final system proof. It must run only after the operator specifically approves **which data sources and applied test imports** are permitted. Never infer that permission from the general phrase "test as a whole".

If authorized, use **one new guarded Enterprise clone** and the existing canonical importer commands/approved harness, all bound to the same approved SHA. The intended sequence is:

1. Establish an independently auditable, **read-only** ERP SQL Server source and allowed VanillaSoft test source, credentials/floors, permitted scope and redaction rules. If only sanitized synthetic sources are approved, label the evidence SYNTHETIC rather than live-source proof. Do not query operational providers merely to make the test green.
2. Use the **existing canonical ERP importer**, in its actual supported order, against the owned clone. It may load counterparties, facilities, contacts, salespeople and commercial documents in one full invocation. **Do not artificially split the ERP import around the CRM run**, or force a second applied import onto a non-empty database, unless the exact staged/reload path is explicitly documented and separately approved. If using a bounded worksheet limit, prove that the selected fixtures actually include the intended edge cases. Keep source provenance and counts.
3. Through the **existing** authorized VanillaSoft CRM importer/harness, import overlapping approved contacts, material profiles, calls and notes **into that same ERP-populated clone**; prove no duplicate persons or dropped history, correct owner mapping and ERP field precedence.
4. Inspect the commercial documents **already realized by the canonical ERP run**: multi-worksheet orders, inbound inventory purchases without sales, PayablesBatch headers and child bills, terms/dates, credits and previously approved special cases. Verify buyer/seller links, source reconciliation and that no unauthorized stock, posting, payment or settlement events were manufactured. If the bounded import lacked an edge case, mark that case NOT_PROVEN, not PASS.
5. Replay the same authorized source inputs **only through an existing supported, separately approved replay path** against the same owned clone. A default importer empty-database guard is **not** permission to override it. Compare stable record identities, counts, relationships, material identities, source fields, financial totals, date/due-date decisions, draft/posting policy and reasoned anomaly census. Record every drift or duplicates, including differences explicitly caused by the still-undecided existing-document replay policy. Do not choose a replay policy or overwrite existing documents on Cursor's initiative.
6. Preserve before/after state digests, detailed redacted reports, command exit codes and source coordinates. Retire only the owned clone with the canonical guarded drop command. No live Odoo.sh write, source update, direct payment or posted accounting.

If approved data/connectors or an **existing safe same-clone harness** are unavailable, mark `I4 = BLOCKED_OR_NOT_PROVEN`, identify the precise missing dependency, and **STOP**. Do **not** fabricate test inputs, author new test scripts, change any importer code or treat separate module tests as a substitute. The operator may decide later to authorize an exact minimal test addition or one bounded applied import.

## I5. Cohesion verdict, regression routing and release readiness

Give **separate** verdicts for all of these questions:

| ID | Question | Minimum actual proof |
|---|---|---|
| I-A | Is the combined code exactly what the operator accepted? | Integrated SHA, PR-to-integration mapping, clean tree and authorized scope |
| I-B | Do the CRM/ERP source contracts coexist? | Pure tests and path-by-path assertion receipts on integration SHA |
| I-C | Do import-facing Odoo addons load and pass together? | One Enterprise clone and one guarded comma-scope module run, nonzero method-level evidence |
| I-D | Does CRM persistence and watermark behavior still work in the combined code? | F1-F3 runtime receipt on combined SHA |
| I-E | Are ERP and CRM data joined correctly on shared records? | Actual same-clone ERP -> CRM identity and history evidence (I4) |
| I-F | Are orders, bills and historical operational/financial side effects faithful on that same clone? | Source-to-Odoo reconciled rows, no phantom effects (I4) |
| I-G | Is identical whole-system replay deterministic? | Same-source replay on same clone, measured identity and amount invariants (I4) |

Permitted top-line labels: `COMBINED_RUNTIME_PASS`, `COHESION_PASS`, `FAIL`, `NOT_PROVEN`, `BLOCKED`. **`COHESION_PASS` requires all I-A to I-G to have sufficient actual evidence at the one approved integration SHA.** A passing I2/I3 with I4 unexecuted is only `COMBINED_RUNTIME_PASS; END_TO_END_NOT_PROVEN`. No business-fidelity assertion follows automatically from an importer-test green result.

On a real integration failure, provide the minimal cross-PR counterexample and earliest wrong boundary. State whether the defect was present individually, newly induced by combination, or was never covered. Prioritize material data loss, identity misbinding, wrong ledger dates/amounts, duplicate history and false-success summaries ahead of diagnostic polish. All proposed changes remain **`PENDING_OPERATOR_APPROVAL`**. Cursor may not edit, merge, create a PR, publish, or automatically rerun after fixes; each new approved commit invalidates the prior combined evidence and requires a fresh relevant run.

**Stop point:** Deliver the per-behavior integration ledger, one top-level verdict with explicit limits, the SHA-bound receipts, and the operator's approval queue. Never keep testing or fixing indefinitely.
