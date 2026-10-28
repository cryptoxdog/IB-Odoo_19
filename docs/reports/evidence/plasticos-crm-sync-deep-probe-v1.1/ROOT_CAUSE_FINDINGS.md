# Root cause findings

## MAT-STATUS-01

- finding_id: MAT-STATUS-01
- severity: S1
- affected behavior IDs: MAT-07, RUN-05
- exact repo SHA: 83f6ff9516e99fd8d2f864dab16078103e231e42
- proof classification: CONFIRMED
- provider endpoint/window or test method IDs: direct call of `build_run_summary` and `SyncOrchestrator._completion`. ORM methods `TestCrmSyncOrchestrator.test_unresolved_material_is_reported_without_a_profile` and `test_approved_material_failure_is_contained_and_the_page_continues` also passed while asserting `outcomes["failed"] == 0` with a material `error_rows` entry. No provider call. No stored `plasticos.crm.sync.run` assertion.
- observed vs expected: a material error is recorded and the contact-failure counter stays 0. Both classifiers return `success`. Expected classification for a required material failure is not `success`.
- witness and denominator: 1 synthetic material error row in the direct call; 0 contact failures; 0 call failures. The ORM suite was 105 tests, 0 failed, 0 errors, and those two methods are among the passes. Their pass confirms the current counter behavior. It does not prove a durable run row.
- first wrong boundary and symbol: `plasticos_crm_sync/services/import_summary.py:build_run_summary` and `plasticos_crm_sync/services/orchestrator.py:_completion`. `_apply_approved_materials` appends material text to `error_rows` without incrementing `outcomes["failed"]`.
- alternative causes discriminated: the direct call did not write a database row. The ORM tests did write synthetic leads on the owned clone and still left the failure counter at 0. That discriminates the counter from a missing test harness. It does not discriminate a later status write that this suite does not assert.
- status impact: `CRM_PROMOTION` cannot pass while a material-only error is classified `success`.
- smallest proposed code-owner correction: teach `_completion` and `build_run_summary` to treat material `error_rows` as a non-success outcome, and change the ORM tests that currently require `outcomes["failed"] == 0` for that case. Not applied in this diagnostic.
- failing discriminating regression after approval: `TEST_EXECUTION_RECEIPTS/material-status-falsifier.txt`, promoted to a collected test that expects a non-success status.
- external dependency: none for the classification. A stored-run witness can be added on the existing owned clone without a new template.
- operator decision: none required to keep the finding.
