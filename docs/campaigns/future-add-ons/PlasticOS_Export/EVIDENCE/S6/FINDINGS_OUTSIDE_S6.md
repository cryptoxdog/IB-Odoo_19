# Findings outside S6 effects (returned to GAR, not fixed here)

These come from the C06 locked invariant: a defect outside S6 effects is reported, not fixed. Each finding carries the evidence that classifies it.

| Id | Where | Class | Evidence | Suggested owner fix |
|---|---|---|---|---|
| D1 | `plasticos_documents/migrations/19.0.2.1.18/post-migrate.py` | Witness defect: the counter is wrong, the outcome is correct | On the seeded clone, the census recorded 8 rows / 6 accepted / 6 decided. Post-migrate logged "0 rows classified legacy", yet all 8 rows are `legacy` and the provenance digest is unchanged. `obligation_kind` is `required=True, default='legacy'`, so the ORM fills the new column before post-migrate runs and `UPDATE … WHERE obligation_kind IS NULL` matches 0 rows. | Report the number of `legacy` rows after the update, or carry the pre-migrate NULL/absent count in the census |
| D2 | `plasticos_export` module description | Nit | Loading the module prints docutils `<string>:11: (ERROR/3) Unexpected indentation` plus two WARNINGs | Fix the RST in the description |
| D3 | `plasticos_material_profile` `TestMaterialNormalizer.test_approved_vanillasoft_aliases_resolve_every_master` | Pre-existing Staging test failure | The test fails on a clean Staging clone at `08504e12` with no campaign code, and on both upgraded clones. Line 223 expects `normalize_material(env, "PET Bottles").unresolved == ("unresolved material",)` and gets `()`. The campaign leaves the module unchanged: `git diff 08504e12..0c142374` is empty. | Owner: the material profile normalizer |
| D4 | `plasticos_enrichment` `TestInjectBatchQueries.test_material_inject_looks_profiles_up_once_and_merges_a_repeated_identity` | Pre-existing Staging test failure | Same evidence as D3. Line 103 expects one profile and finds 0. | Owner: enrichment inject |
| D5 | `plasticos_transaction/tests/test_erp_worksheet_import.py:223-224` `_snapshot()` | Test isolation (7 errors on data that already exists) | The test sorts `origin` values from every sale and purchase order. When an order has `origin = False`, the sort raises `TypeError: '<' not supported between str and bool`. The test passes on the unseeded control clone. | Sort with a key that orders `False` first, or scope the snapshot to the test's own records |
| D6 | `plasticos_logistics/tests/test_load_cardinality.py` (two tests that replay 19.0.1.14.6) | Test isolation | The tests replay the 14.6 migration over the whole table. They refuse on seeded multi-load parents whose legacy `plasticos_transaction.load_id` names the first load. That is a real post-14.6 Staging shape. The tests pass on the unseeded control clone. | Scope the replay to the test's own rows |
| D7 | `plasticos_logistics/tests/test_linda_freight_models.py` (four tests) and `test_load_cardinality.py::test_acknowledgment_job_escalates_without_resending_the_packet` | Test isolation | The tests assume they own every eligible load. The global ACK page (200) is filled by the 240 seeded dispatched loads. The tests pass on the unseeded control clone. | Pass the test loads explicitly, or set `linda_load_sweep_batch` in the context |
| D8 | `plasticos_logistics/models/mail_mail_inherit.py:111` `_linda_claim_outgoing` | Robustness | When a request has no mail, the query runs `… WHERE mail_id = false`, which raises psycopg `UndefinedFunction: integer = boolean`. It is reached only through the starved path in D7. | Guard an empty mail record before the SQL |

Classification runs (logs are kept outside the repository):

- Seeded and upgraded `odoo_test_s6up`: 1565 run, 6 failed, 10 errors. These are D3–D7.
- Unseeded and upgraded control `odoo_test_s6ctl`: 1565 run, 2 failed, 0 errors. These are D3 and D4.
- Clean Staging `odoo_test_s6stg`, no migration: D3 and D4 fail (material_profile 35 run, 1 failed; enrichment 18 run, 1 failed).
