## v2.4.0 execution discipline

- Test M301, M303, and BOTH from `00_READ_FIRST.md`. Follow `07_EXACT_PREFLIGHT_AND_RUN_COMMANDS.md` for the fixture. The database names below are examples.
- Score catalog IDs only. A method that did not run is `NOT_PROVEN`.
- On the first failing assertion, save the log and continue any lane that does not depend on that failure. Do not patch the failure.
- BOTH runs in this campaign. It is the pre-merge combined tree, built locally and not pushed.

# 03. Cursor execution: small independent slices, no code changes

## Absolute preconditions

Finish `01_SOURCE_AND_FIXTURE_ADMISSION.md` **for each separate worktree**. If its exact SHA, Enterprise parity, fixture `ready`, mount binding, source cleanliness or owning Docker identity is not proven, **DO NOT EXECUTE ITS TESTS**. Do not repair the environment, rebuild anything, choose Community, or borrow another PR's test receipt.

Run one worktree at a time. Each slice below is a **question**, not a license to modify code. The smallest **supported** Odoo runtime command is `make test-module m=<addon>`, which runs that addon's registered tests against a fresh owned clone. Do **not** bypass `scripts/test_env.sh` to force a single method. For each behavior, prove that the named method/assertion actually ran; if method-level evidence is absent, its individual verdict is `NOT_PROVEN` even if the module summary is green.

## Phase 0. Environment and revision bindings for all three lanes

1. Query GitHub for open PRs touching `plasticos_partner_import`, `plasticos_crm_sync`, related CRM/ERP material models, or `plasticos_transaction`. Record exact base/head SHA and changed files. Do not include #302 logistics or #296/#297 publication/indexing just because open.
2. Create three **separate detached worktrees** as in document 01: S (`Staging`), 301, 303. Check SHA and clean tree for each.
3. For each, verify Compose `/mnt/extra-addons` maps to that worktree, `/mnt/enterprise` to the existing Enterprise source, and `config/test_env_fixture.conf` to the same canonical fixture.
4. Record existing database/container, image ID and template admission. Do not call the template/build lifecycle. If one worktree's fingerprint or admission does not match, its lane is BLOCKED; others remain independently assessable.
5. Catalog the registered tests by checking each addon's `tests/__init__.py`, not simply a root `tests/` file's presence. Flag root Odoo test modules not registered by Odoo as `NOT_COLLECTED`, without attempting to move them.

## Phase S. Merged ERP/CRM import baseline (CWD = isolated `Staging` worktree)

### S1. ERP reader, source keys, ownership and diagnostics (pure Python)

```bash
python3 -m pytest -q tests/test_erp_source_layer.py -k 'payables_batch or inventory_destination or sales_rep or contact'
python3 -m pytest -q tests/test_erp_mapping_status.py tests/test_erp_summary.py tests/test_erp_layer_gate.py tests/test_erp_import_limit.py
python3 -m pytest -q tests/test_erp_import_contract.py
```

Read individual method verdicts for S-C1, S-E1, S-E2, S-E3. A missing test (`0 collected`) is NOT_PROVEN, not PASS. A discrepancy between frozen source counts and the later live restore is an unresolved source-data discrepancy, **not** authorization to rewrite counters.

### S2. Contacts, owners, call links, CRM completeness (pure Python)

```bash
python3 -m pytest -q tests/test_erp_import_contract.py tests/test_crm_approved_identity.py
python3 -m pytest -q tests/test_vanillasoft_owner_crosswalk.py tests/test_crm_history_links.py
python3 -m pytest -q tests/test_crm_sync_classification.py tests/test_crm_sync_mapping_status.py
python3 -m pytest -q tests/test_crm_sync_full_import.py tests/test_crm_sync_completeness.py tests/test_crm_sync_vanillasoft_client.py
```

Report S-C1 through S-C6 separately. Especially distinguish (a) existing ERP person preserved, (b) approved VanillaSoft history routed to that person, (c) disabled numbers absent, (d) owner login unchanged, and (e) truthful full-history watermarks. One green `pytest` command never proves every one of these unless its corresponding test actually ran.

### S3. Registered Odoo ORM behavior on Enterprise (one **fresh named clone per module**, not per PR)

Only after the fixture is READY. **Before each run verify that the proposed clone name is absent** from the existing DB list, to prevent replacing a prior run's artifacts. Names below are examples; append a unique run suffix if occupied and update the report.

```bash
make test-module m=plasticos_partner_import ODOO_TEST_DB=odoo_test_s_partner_a
make test-module m=plasticos_crm_sync ODOO_TEST_DB=odoo_test_s_crm_a
make test-module m=plasticos_material_profile ODOO_TEST_DB=odoo_test_s_material_a
make test-module m=plasticos_transaction ODOO_TEST_DB=odoo_test_s_transaction_a
```

Capture all four corresponding `.test.log` and `.test-receipt.json` files separately. Distinguish `plasticos_partner_import`'s currently **registered** tests from root Odoo tests not registered in S. For S-E1, verify the specific inbound-to-inventory test ran. Keep logistics test tags excluded. After saving evidence, retire each owned clone separately through `bash scripts/test_env.sh drop <same_name>`; never drop templates or shared DBs.

### S4. High-yield CRM integration check (synthetic only)

If previous CRM slices are clean and fixture still READY:

```bash
make runtime-gate-f1
make runtime-gate-f1-accept
```

This is the repository's F1-F3 **synthetic** real-Odoo/PostgreSQL admission, not a live VanillaSoft import and not F4/F5. Its receipt must be tied to the same `Staging` SHA, with the owned clone confirmed retired. If it is inapplicable, mark NOT_RUN with reason. Never invoke a real VanillaSoft API import to manufacture coverage.

## Phase M301. Staging merged with PR #301

CWD is the M301 worktree, not the raw #301 tip when that tip does not contain `Staging`.

### 301-P: Minimal pure checks (each behavior individually)

```bash
python3 -m pytest -q tests/test_erp_native_orders.py -k 'vendor_bill or term or delivered_basis'
python3 -m pytest -q tests/test_erp_native_document_guard.py
python3 -m pytest -q tests/test_erp_mapping_status.py
```

Map results onto catalog IDs `301-A` through `301-I`. A pure test is not ORM proof. Do not add tests to fill a gap.

### 301-R: Real Odoo ORM only on this PR's Enterprise clone

```bash
make test-module m=plasticos_transaction ODOO_TEST_DB=odoo_test_pr301_tx_a
```

Prove the two new `TestErpWorksheetImport` methods executed, not merely collected:

- `test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event`
- `test_delivered_basis_sets_no_incoterm_and_undated_invoice_stays_undated`

For each claimed behavior record exact assertion/record values in redacted form, and a separate PASS/FAIL/NOT_PROVEN. Particularly do **not** infer an undated **vendor** bill behavior from an undated **customer** invoice assertion. Capture module exit and raw Odoo failure/error count even if a different case fails. Retire only `odoo_test_pr301_tx_a` (or the unique name used) through the guarded drop command.

**No cross-branch import execution:** Do not attach #303's relocated tests to #301, do not modify `tests/__init__.py`, manifests, or Odoo source. Report which #301 behaviors are still untested by the actual Odoo methods.

## Phase M303. Staging merged with PR #303

CWD is the M303 worktree. When the PR head already contains `Staging`, that head is M303. The executable baseline `702ebaf` is history, not the tree under test.

### 303-H: Pinned published evidence and outcome taxonomy (MANDATORY first)

At the selected #303 SHA, read **all five** `docs/reports/evidence/pr303-cursor-handoff/{README.md,claims-recovery-brief.md,offer-acceptance-brief.md,security-acl-brief.md,enterprise-validation.md}`. Verify the `702ebaf..190c497` transition contains exactly those five additions. Inventory the **seven distinct known failing test IDs** and the one `TestErpWorksheetImport` setup error. Record them as **REPORTED_CE, NOT_YET_ENTERPRISE_VERIFIED** until the actual Enterprise module emits method-level evidence. The expected-failure inventory is separate from the import-focused module-run acceptance: failures remain visible even if their modules are excluded from the authorized logistics-free test selection. Do not broaden into claims/offer/commission/logistics module test runs because the guarded runner may also select logistics-coupled tests. An operator may separately approve a safe narrowed test mechanism later; Cursor cannot invent one.

**One diagnostic success rule:** a well-evidenced report identifying the seven known issues, the accounting XMLID result, unexpected ACL PASS, and compliance/auto-posting risk is a valid **DIAGNOSTIC_COMPLETE** outcome, despite intentionally unresolved test failures. It is **not** PR-ready/merge-ready. `MERGE_READY=NO` until scope, business role policy, stale test contracts, production-gate changes, and integration collision each have approved dispositions and any authorized code/test edits are independently retested.

### 303-P: Verify that test discovery itself is correct (pure Python)

```bash
python3 -m pytest -q tests/test_odoo_test_discovery.py
```

Use only PR #303's copy of that new test. Its static PASS shows import paths appear wired, **not** that every test actually executed. Record method names and any misattribution to a test owner.

### 303-R: Check import-related test owners on the existing Enterprise fixture

```bash
make test-module m=plasticos_partner_import ODOO_TEST_DB=odoo_test_pr303_partner_a
make test-module m=plasticos_base ODOO_TEST_DB=odoo_test_pr303_base_a
make test-module m=plasticos_material_profile ODOO_TEST_DB=odoo_test_pr303_material_a
make test-module m=plasticos_transaction ODOO_TEST_DB=odoo_test_pr303_tx_a
```

**Optional, only if needed to assess an actual import invoice/transaction effect**:

```bash
make test-module m=plasticos_documents ODOO_TEST_DB=odoo_test_pr303_docs_a
```

For 303-A through 303-G, verify expected relocated test IDs run and distinguish test-collection truth from business behavior. Only `plasticos_partner_import`, `plasticos_base`, `plasticos_material_profile`, `plasticos_transaction`, and import-relevant `plasticos_documents` are targets. **Never run `plasticos_logistics`, claims, offer, matching, all-addons sweeps, or unscoped `make test-odoo`.** Required dependency upgrades are not independent logistics testing. Preserve known unrelated failures as out-of-scope observations, not an invitation to fix them.

Do not claim the independent #303 run proves #301 accounting behavior. #303 includes document/transaction product changes not in #301; cross-branch overlap remains untested until a separately authorized integration head exists.

## Phase R. Optional higher-order source-to-Odoo evidence

This plan authorizes the existing synthetic Odoo tests and **read-only** inspection of existing sanitized source material. It does **not** authorize applying a real restored SQL Server import, live VanillaSoft sync, unbounded API reads, posted accounting, payments or settlement. If a result requires direct SQL applied import/replay, capture: desired table/records, proposed exact `make import-erp` invocation, destination owned clone, restored source read-only assurance, expected storage and credential handling, and **request explicit operator approval before running it**. Never substitute a frozen grid for proof of a live SQL restore.

## Stop and report after each lane

- Recheck SHA, Git status, Enterprise fixture fingerprint and image ID. Any unexpected change => STOP and report environmental mutation.
- Save reports **per behavior**, not one aggregate `green` result. Failure of one case does not classify independent cases as failed; never infer their PASS without direct evidence.
- Prioritize the first causally discriminating error over rerunning broad suites. No iterative fix/test loops. No test re-authoring, imports beyond permission, or automatic remediation.
- Retire owned clones with the guarded script and record whether retirement actually succeeded.
- Produce one approval queue: high-impact verified defects, important warnings, inconsistencies, and workflow/policy misalignments. All recommended changes remain unapproved.

## Phase BOTH. Combined pre-merge tree

Run this in the same campaign, on the detached BOTH worktree from `00_READ_FIRST.md`. Do not wait for a later published SHA. Do not push the local merge. Execute the module list in `02_PR_BEHAVIOR_MATRIX.md` and the proof limits in `06_FINAL_COHESION_GATE.md`. A green module run is `COMBINED_RUNTIME_PASS` until a separately authorized same-clone ERP and VanillaSoft import exists.

This last phase has four escalating signals: (1) approved integration content and same-Enterprise-fixture proof; (2) targeted cross-boundary pure assertions; (3) **one simultaneous, import-facing multi-addon Odoo runtime run on a fresh owned clone** plus existing F1-F3; and (4) actual **ERP -> CRM -> commercial records -> identical replay within one guarded Enterprise clone**, only if its applied-test imports/data sources are separately authorized. The guarded multi-addon test run is not a surrogate for same-record-graph replay.

Exit with `COMBINED_RUNTIME_PASS` only when integration load/methods pass, and with `COHESION_PASS` only when real same-clone cross-system behavior also passes. If authorization, test collection, or an integrated SHA is missing, say `BLOCKED`/`NOT_PROVEN`, preserve the precise missing evidence and stop. No code changes, fixture manipulation, Git merge, logistics tests, or automatic remediation.

### 303-Q: Small, decisive Enterprise questions (only on the admitted disposable clone)

1. **Accounting seed, not a fix:** before evaluating `TestErpWorksheetImport`, inspect `ir.model.data` on the **test clone** for `plasticos_accounting.account_40050_sales_income` and associated required account XMLIDs. Record whether they existed **before** the ORM test command and after its permitted test-addon upgrade. Do not reseed or rerun an upgrade directly against the Enterprise template to make it green. If missing, report the stage and cause as environment hypothesis or confirmed environment failure; do not automatically call it a code defect.
2. **Document compliance and posting:** trace `_compute_compliance` (unscoped), `_auto_post_pending_invoices`, `account.move.action_post()` (`purpose=invoice`), and `action_close(required_for_close)` in the #303 tree. Existing Odoo tests can establish parts of these paths; **if no existing test executes the cross-path state transition, mark real runtime interaction NOT_PROVEN**, do not add a new test or artificially post a historical bill. This matters because #301 preserves historical invoices as drafts. That code is absent from M303 and present on BOTH, which is why BOTH is a separate tree.
3. **ACL unexpected PASS:** report the CE-observed pass for `test_base_user_cannot_unlink` and determine whether an existing authorized Enterprise test/method or read-only effective-permission inspection exposes the first `AccessError` origin. Do not attribute it to a guessed record rule; if the targeted method is not safely executable without unrelated logistics/claims tests, classify `BLOCKED_SCOPE / NOT_PROVEN`.
4. **Discovery:** distinguish the CE-reported 605 executed relocated tests and 807 total suite tests from what the **selected import-only Enterprise tags actually execute**. Those counts are comparator evidence, not required Enterprise thresholds. Do not claim all 39 moved files executed if the campaign excludes the logistics/other module tags.

Each of these returns a separate report status. The seven red CE tests, expected-passing ACL unlink, and one CE accounting error remain on the diagnostic board even if the selected import modules pass.
