# CRM sync deep probe v1.1

Pinned source: `83f6ff9516e99fd8d2f864dab16078103e231e42` (`origin/Staging`). Detached worktree `wt-crm-deep-probe-v11` was clean before and after the Enterprise run. Pack revision 1.1.3 is in the operator checkout and was not part of the tested tree.

DIAGNOSTIC=COMPLETE
CRM_PROMOTION=NOT_PROVEN

## What was wrong

The results validator resolved the repository with `pack.parents[4]`, which is the parent of this clone, so it rejected the only legal evidence directory. The safety text also stopped the Enterprise lane when a dry run could not prove `docker compose build` was cache-only. The existing runner always builds during initialization. That is ordinary startup, not a reason to skip the lane.

## What ran

- Pure pytest, unchanged: 208 passed, 1 skipped. The skip is the absent operator crosswalk file.
- Direct call of `build_run_summary` and `SyncOrchestrator._completion`: one material error row, zero contact failures, both returned `success`. Finding `MAT-STATUS-01`.
- `make test-module` for `plasticos_crm_sync,plasticos_crm_bridge,plasticos_material_profile,plasticos_facility_profile,plasticos_partner_import` on clone `odoo_test_w9c463fadbf`. Native receipt: 105 tests, 0 failed, 0 errors, exit 0, `dirty` false, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`.

## Counts

43 rows dispositioned. 17 technical PASS on synthetic ORM or pure witnesses, with business NOT_PROVEN because no live source population was read back. 2 technical FAIL (`MAT-07`, `RUN-05`). 24 technical NOT_PROVEN. No business PASS.

## Limits

No VanillaSoft request was made. The 96-field workbook was not recovered. No owned-clone import or identical snapshot replay ran. `MAT-STATUS-01` is confirmed for the classifiers and for the ORM upsert counter (`outcomes["failed"]` stays 0). A stored `plasticos.crm.sync.run` row was not the witness, so that durable status is still not proven. The owned clone was left in place.
