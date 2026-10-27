# GMP-129 — MAT-STATUS-01

**Task:** A persisted VanillaSoft contact whose required material mapping did not land is `partial`, not `success`.
**Base:** `origin/Staging` `83f6ff9516e99fd8d2f864dab16078103e231e42`
**Branch:** `fix/crm-sync-mat-status-01`
**Behavior:** MAT-STATUS-01 (probe IDs MAT-07, RUN-05)

## What changed

`_completion` and `build_run_summary` now agree. A required mapping error, including a material failure with `contacts_failed == 0` and `calls_failed == 0`, yields `partial` and a persisted error excerpt. An informational notice is also `partial`, and its excerpt does not claim a required mapping failed. Contact and call counters stay as recorded. `last_success_at` advances only when the run status is `success`.

`business_acceptance` returns `FAIL` for `partial`, `failed`, or a required mapping error. `import_vanillasoft_shell.py` still exits 0 on `partial`.

Empty material input returns before the normalizer import, so a contact with no material text is not recorded as a material failure.

## RED

Before the correction, on this tree:

- `test_a_material_only_error_is_partial_and_replay_does_not_hide_it` — `_completion` returned `success`.
- `test_summary_rejects_success_when_material_errors_exist_and_contact_failures_do_not` — `build_run_summary` returned `success` with one error and `contacts_failed == 0`.
- `test_an_informational_notice_stays_partial_without_claiming_a_required_mapping` — `_completion` returned `success`.
- `test_a_watermark_older_than_the_lookback_makes_the_run_partial_and_names_the_gap` — a `partial` run set `last_success_at`.

## GREEN

Pure pytest: `tests/test_crm_sync_completeness.py`, `tests/test_crm_sync_full_import.py`, `tests/test_crm_sync_mapping_status.py`, `tests/test_crm_sync_classification.py` — 101 passed.

Enterprise ORM, fixture `odoo_test_tpl_ee_c9e8a81f52f23680`, clone `odoo_test_wbb69f8a9ba`: `make test-module m=plasticos_crm_sync fresh=0` — 58 tests, 0 failed, 0 errors. `test_material_only_failure_is_persisted_partial_and_replay_preserves_erp_values` and `test_unresolved_material_is_reported_without_a_profile` ran in that set. The first Enterprise attempt failed only because `res.partner.comment` is HTML (`<p>ERP-OWNED-SENTINEL</p>`); the assertion now checks that the sentinel text remains.

## Not in this PR

No source column was newly mapped. The other v1.4 corrections, the 24 real-data obligations, and the pinned crosswalk acceptance are still open. This PR does not merge or deploy.
