# v1.1 improvements over v1.0

1. **Five Enterprise clone runs -> one combined CRM lane** using the runner's proven comma-separated scope; only isolate failed tests when diagnostic value justifies the extra clone. Historical transaction/PR303 tests are not transplanted.
2. **Correct native receipt semantics:** repo's JSON receipt does not contain image/PG/Enterprise identity or method census. Require independent image/DB pre/post attestation and parsed method IDs from raw logs.
3. **No unsafe `status` assumption:** `test_env.sh status` performs `compose up` and `compose build`. A preexisting Docker image does not prove cache-only behavior. Harden preflight to fail closed if no-mutation assurance is unprovable.
4. **Native guarded real import invocation:** confirmed `test_env.sh run <clone> -- make import-vanillasoft ODOO_DB_NAME=<clone> VANILLASOFT_CALL_FLOOR=... VANILLASOFT_CONTACT_FLOOR=...`, rather than an unguarded `make import-vanillasoft` that can hit a different DB/runtime.
5. **Source gap containment:** historical `/Contacts` restriction blocks full-census acceptance only; static, pure and independent ORM probes can still complete. A provider sample is not a full source inventory.
6. **Actual user intent separation:** approved 96-field dispositions vs 44 pending, canonical multi-material profiles, existing ERP-person integrity, owner login, full-history identities and run-status truth. Zero authorization to remap optional fields.
7. **Bounded execution + two verdicts:** one independent discovery pass and one verification pass; output distinguishes `DIAGNOSTIC` from `CRM_PROMOTION` (source completeness and business correctness).
8. **Run-ready structural validator:** `validate_results.py` checks all original behavior IDs, statuses, evidence locators, missing proofs, and source ledger shape without claiming tests actually ran. Nothing is silently marked green.
9. **Privacy hardened:** local raw logs and private ID joins stay private, exported material uses HMAC tokens, a redacted report, and explicit secret/PII inspection before sharing.

## v1.1.1 defect closure

10. **Probe names match the tree.** `HIS-01` points at `tests/test_crm_sync_full_import.py::test_a_person_binding_keeps_call_history_on_that_partner`. `RUN-03` points at that file's `test_a_manually_archived_lead_is_not_reactivated_without_sync_provenance` and `plasticos_crm_sync/tests/test_lead_lifecycle.py::test_manually_archived_odoo_lead_is_not_reactivated_without_sync_provenance`. `tests/test_crm_history_links.py` is not a candidate.
11. **Material false-green is not a green unit test.** `test_unresolved_material_is_reported_without_a_profile` asserts `error_rows` with `outcomes["failed"] == 0`. `test_committed_sync_metrics.py` covers page counters. `MAT-07` and `RUN-05` PASS only from a `_completion` / `build_run_summary` witness.
12. **Combined lane coupling is explicit.** Partner-import access tests and facility uniqueness tests ride the same receipt. A failure there does not by itself fail a CRM catalog row.
13. **Runner side effects named.** A pinned-fixture re-stamp is a stop. `VANILLASOFT_REPORT_PATH` is mandatory for this campaign because `parse_run` allows omitting it, and the Makefile default writes `.l9/pr/import-vanillasoft-summary.json` inside the worktree.
14. **Validator matches the evidence contract.** It checks the two verdicts once each, provenance keys, receipt directory, enterprise/clone PASS paths, finding IDs, ledger identity and disposition, census tokens, promotion gates, and shareable secret/email strings. The execution contract is in `MANIFEST.json`. Zero validator issues still do not prove the tests ran or that promotion is earned.

## v1.1.2 evidence location

15. **Results are tracked campaign files.** The evidence directory is `docs/reports/evidence/plasticos-crm-sync-deep-probe-v1.1/`. `git add` covers every file in it, including native `.test.log` files. Repo `.gitignore` negates the global `*.log` exclude for `docs/reports/evidence/**/*.log`. `.DS_Store` stays ignored. `validate_results.py` rejects any other directory and any non-`.DS_Store` file that is not in `git ls-files`.

## v1.1.3 probe repair

16. **Git worktree discovery.** `validate_results.py` no longer assumes `pack.parents[4]`. The repository root is `git rev-parse --show-toplevel` from the pack directory, so a detached worktree resolves to that worktree and the evidence directory must be `docs/reports/evidence/<campaign>/` inside it. The 43-row catalog and the other structural checks are unchanged.
17. **Ordinary image build is authorized.** Item 3's cache-only stop is superseded for this revision. `scripts/test_env.sh` may run `docker compose build --quiet odoo`. Record image ID and content identity before that build and again before tests. A changed content identity stops the lane before tests. The admitted template `odoo_test_tpl_ee_c9e8a81f52f23680` is not created, rebuilt, renamed, or replaced. A re-stamp of that template remains a stop.
