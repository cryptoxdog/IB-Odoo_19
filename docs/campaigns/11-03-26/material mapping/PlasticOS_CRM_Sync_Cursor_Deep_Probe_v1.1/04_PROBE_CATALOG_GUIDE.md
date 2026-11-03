# Why these 43 probes, and exactly what they can prove

The CSV is the frozen diagnostic obligation list. `priority=GATE` marks launch-critical evidence, not permission to skip `REQUIRED` rows. Its `evidence_lanes` column shows which independent evidence classes would discriminate the behavior. **One combined ORM test run can satisfy several rows**, but individual row PASS still requires an actually executed method/assertion or independent source-target witness. When the available test does not exercise the production path, mark `NOT_PROVEN` or `NOT_COLLECTED` rather than modifying tests.

## High-yield first falsifiers

1. `SRC-01`: a full historical ContactID inventory independent from rolling `/Contacts` lookback (API 31+ days previously HTTP 400). Determine *which existing supported* provider export / read-only route makes this possible; do not invent an endpoint. Count-only exports do not prove full field fidelity.
2. `MAT-07`, `RUN-05`: introduce one material-bearing contact with unsupported phrase on an isolated synthetic clone. Does `error_rows` record it while durable `plasticos.crm.sync.run.status` still becomes `success`? Compare `build_run_summary` and the actual profile count. Keep this as an explicit acceptance failure if reproduced.
3. `MAT-08`, `SRC-06`, `SRC-07`: prove actual source location of required materials. If custom-table `get_custom_tables_list` or `get_custom_table_data` fails while `CUSTOM_TABLES_REQUIRED=False`, does it yield empty material evidence and a green run? Separate missing row `data_id` behavior from transport outage.
4. `MAP-01`, `MAP-02`: test every **actual** owner-email value against `owner_crosswalk.py` and persisted `res.users.login`; distinguish `ss@` -> Mack and Tiffany `sa@`. Verify backfill on existing leads without clearing valid assignment.
5. `ID-01`–`ID-05`: confirm approved person crosswalk version, 28 historical missing-ERP-person statuses, non-approved standalone leads and no orphan external refs. Don't relax inactive-contact eligibility simply to reduce failures.
6. `MAT-01`–`MAT-06`, `MAT-09`–`MAT-10`: preserve n distinct `(polymer,form)` pairs and null form, attach to correct owning facility, detect ambiguous facility, keep evidence of grade conflicts, prohibit guessed aliases.
7. `TST-01`, `TST-02`: distinguish collected pure tests, addon-registered ORM tests and uncollected root ORM tests. A module green is not evidence that every behavioral test was reached.

## Actual test discovery candidates (verify methods before running)

Pure examples: `tests/test_crm_sync_full_import.py`, `tests/test_crm_sync_completeness.py`, `tests/test_crm_sync_vanillasoft_client.py`, `tests/test_crm_sync_classification.py`, `tests/test_crm_sync_mapping_status.py`, `tests/test_crm_approved_identity.py`, `tests/test_vanillasoft_owner_crosswalk.py`, `tests/test_crm_history_links.py`, `tests/test_committed_sync_metrics.py`, and contact-only selections from `tests/test_erp_import_contract.py`/`tests/test_erp_source_layer.py`.

ORM examples: registered `plasticos_crm_sync/tests/test_orchestrator_upsert.py` (including methods named `test_unresolved_material_is_reported_without_a_profile`, `test_three_source_materials_become_three_profiles_and_replay`, `test_unknown_form_creates_one_profile_and_replays`, `test_locked_owner_emails_persist_on_the_lead_and_replay`) and `plasticos_material_profile/tests/test_material_normalizer.py`. Confirm class and import chain on pinned revision; don't trust a filename-only census.

## Minimal work rule

Do one pure pass, **one multi-addon Enterprise invocation**, one bounded provider path/census interrogation, and at most one E2E/replay sequence if safe. Extra probes only to discriminate unresolved material owner/path, not to make reports longer. If a source blocker makes a behavior impossible, classify it early and preserve time for independently testable ORM and field-mapping concerns. Never lower required behavior because source is unavailable.
