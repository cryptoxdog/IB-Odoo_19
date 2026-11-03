# PlasticOS CRM Sync | Cursor diagnostic campaign v1.1

**Bottom line:** Diagnose the entire CRM sync vertical and **only its directly exercised dependencies** against exact `cryptoxdog/IB-Odoo_19` `Staging`, inside the already-admitted Odoo 19 **Enterprise** Docker environment. This is **Step 1: probe and report**, never fix, merge, publish, or deploy.

## Operating order

1. Paste `05_CURSOR_PASTE.md` into Cursor from the Odoo workspace.
2. Read `01_SAFETY_AND_PREFLIGHT.md` and stop if its gates are not proven.
3. Read `02_EXECUTION_SEQUENCE.md`; run pure/source-independent probes first, then **one combined, isolated CRM Enterprise module lane** (not five clones). Isolate only genuinely discriminating failures on new clones. Run a second, separate owned E2E clone only when safe.
4. Disposition **all 43 rows** in `CRM_BEHAVIOR_CATALOG.csv` without inventing extra business requirements. Append newly discovered reachable CRM behaviors.
5. Produce the outputs specified in `03_EVIDENCE_AND_CLOSEOUT.md` and validate their structure with `python3 validate_results.py <evidence-directory>`; static validation does not itself prove correctness.

## Exact scope

Core: `plasticos_crm_sync` (adapter, transport, contacts, call history, custom tables, scheduled/manual sync, watermarks, reporting), `plasticos_crm_bridge`, `plasticos_material_profile`, `plasticos_facility_profile`. Direct CRM-read/write seams: `plasticos_partner_import` for approved ERP contact identities; relevant `plasticos_base` sales reps, `plasticos_security_base` ACLs, native `crm.lead`, `res.partner`, `res.users`, Odoo Mail if exercised. `plasticos_transaction` is **read-only identity marker evidence only**. Trace actual calls/fields to choose a narrower subset, never audit unrelated code just because an addon upgrades during test setup.

Excluded: PR #301/#303 transaction/accounting changes or test relocation, Linda logistics, GL/AP/AR, sales/purchase transaction reconstruction, commission, matching/EIE/CEG redesign, autonomous email, production database/hosting, broad refactor. #301/#303 **only contribute test methodology** (SHA/receipt/clone/evidence rigor).

## Known historical evidence, not new acceptance

- Current-at-preparation `Staging` SHA: `2a3b9cda9b127c284d12f98bf35ab0344a500d10`; **resolve again** on start and pin all files/receipts to that exact revision.
- Prior merged CRM fixes: PRs #248, #256, #258, #259, #264, #277, #291, #294, #295. No need to recreate fixes without failing evidence.
- October 18 source probe: VanillaSoft `/Contacts` accepted 30-day lookback, returned HTTP 400 beyond 30 days. Previous approved subset: 763 VS IDs / 716 CT_IDs; 735 mapped, 28 blocked by missing eligible ERP person. These are **historic subset** measurements, not a complete or current population.
- PR #295 reported 96 fields: 15 native, 8 evidence, 11 material, 18 excluded, 44 pending. Treat these as **field-count constraints**; recover exact field identities before making a field-level coverage claim. Do not approve/import all 44 by fiat.
- Current code has `CUSTOM_TABLES_REQUIRED=False`, and material errors can be appended to `error_rows` while `_completion()` only classifies contact/call failures, duplicate identities, buffered orphans and scope. Prove or falsify **false business-green material loss** on isolated tests.

## Hard authority boundary

**Allowed:** read and compare source, tests, repo, logs and supported provider GET requests; create only new owned disposable DB clones via existing guarded mechanism, run tests/imports **into those clones** after prerequisite proofs; create local report artifacts outside the repo. **Forbidden:** edits to application/tests/manifests/fixtures/config/secret maps, bypass/relax assertions, provider writes, scheduler/notification triggers, Docker image or template repair, unbounded live requests, PR/branch publication or merging. No `make test-env`, no `install-smoke`, no test relocation, no alternate Community DB, no raw SQL writes except existing clone runner and explicitly authorized Odoo ORM mutations of owned clone during tests/imports.

If a prerequisite fails, mark the dependent lane `BLOCKED` and continue only independent read-only lanes. Neither diagnostic completion nor individual test success means `CRM_ACCEPTED`.
