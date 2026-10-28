# Next coding contract candidates

No product code was edited.

1. After operator approval, change `build_run_summary` and `_completion` so a material-only `error_rows` entry cannot yield `success`. Update `test_unresolved_material_is_reported_without_a_profile` and `test_approved_material_failure_is_contained_and_the_page_continues`, which currently assert `outcomes["failed"] == 0` for that case. Add a collected regression that fails when `final_status` stays `success`.

2. Recover the approved 96-field workbook and an independent full-history ContactID export before any field-disposition or census claim. Do not approve the 44 pending fields from this ledger. Do not treat a 30-day provider window as the historical population.

3. On a separate owned clone, run one guarded import and an identical snapshot replay only after read-only source access is bound without printing the credential. Partner-import and facility-uniqueness failures on a combined receipt must not be copied onto unrelated CRM rows.

4. Code owner for the status defect is `plasticos_crm_sync` (`services/import_summary.py`, `services/orchestrator.py`).
