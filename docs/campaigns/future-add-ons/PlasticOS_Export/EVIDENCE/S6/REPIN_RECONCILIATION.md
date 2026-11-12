# Repin reconciliation at the slice base (validation obligation 0)

Command, read-only, git objects only:

`python3 -I EXPORT_BRS/INTEROP/tools/repin_overlay.py <repo> <pack> 0c142374913f99452ab2c1fa23f2c056a8c1cf32 <out>`

The repository had to be deepened first with `git fetch --depth=2000 origin Staging`, because the v2.7.5 head `677d734f` was missing from the shallow clone. The result has 412 commits since v2.7.5 and drift policy FAIL_CLOSED_RECONCILE_NEW_DIFF.

| Path (C06 in_scope) | Disposition | Drift since v2.7.5 | S6 reconciliation |
|---|---|---|---|
| scripts/check_module_wiring.py | NO_CHANGE | CHANGED | Byte-identical to the base in the S6 diff |
| ci/check_circular_deps.py | NO_CHANGE | UNCHANGED | Byte-identical |
| plasticos_transaction/models/transaction.py | NO_CHANGE | CHANGED | Byte-identical |
| scripts/get_odoo_module_order.py | NO_CHANGE | UNCHANGED | Byte-identical (fingerprint input) |
| plasticos_security_base/security/security_groups.xml | NO_CHANGE | UNCHANGED | Byte-identical |
| plasticos_transaction/models/native_document_import.py | NO_CHANGE | CHANGED | Byte-identical |
| plasticos_claims/tests/test_state_machines.py | EDIT | CHANGED | Not edited. It passes on upgraded, control and fresh data, so the combined chain requires no edit |
| plasticos_claims/tests/test_integration_flows.py | EDIT | CHANGED | Not edited, same reason |
| plasticos_security_base/tests/test_action_methods.py | EDIT | CHANGED | Not edited, same reason |
| plasticos_commission/tests/test_golden_flows.py | EDIT | CHANGED | Not edited, same reason |
| plasticos_documents/tests/test_account_move_transaction_link.py | NO_CHANGE | CHANGED | Byte-identical |
| plasticos_documents/tests/test_exact_association.py | NO_CHANGE | REMOVED_SINCE_V2_7_5 | Absent at the base and still absent |
| plasticos_documents/tests/test_native_verification_delegation.py | NO_CHANGE | REMOVED_SINCE_V2_7_5 | Absent at the base and still absent (its successor is `plasticos_documents_native/tests/test_verification_delegation.py`) |
| plasticos_documents/tests/test_pr322_findings.py | NO_CHANGE | CHANGED | Byte-identical |
| plasticos_documents/tests/test_verification_writer.py | NO_CHANGE | CHANGED | Byte-identical |
| plasticos_transaction/tests/test_compliance_does_not_post.py | NO_CHANGE | UNCHANGED | Byte-identical |
| plasticos_transaction/tests/__init__.py | NO_CHANGE | CHANGED | Byte-identical |
| scripts/test_env.sh (C06-SCOPE-1) | EDIT | CHANGED | Edited for F4, F8 and F9 |
| tests/test_test_env_safety.py (C06-SCOPE-1) | EDIT | CHANGED | Append-only for every test that predates S6: 416 lines added, 0 removed. One line was added inside an S6-authored test: the source acknowledgement, disclosed on PR #480 |

Three modules are version-bumped once each, because S6 changes their runtime code, data or migration: plasticos_documents 19.0.2.1.18 → 19.0.2.1.19 (D1), plasticos_export 19.0.1.1.0 → 19.0.1.1.1 (D2), and plasticos_logistics 19.0.1.14.21 → 19.0.1.14.22 (a, D9 and N1, one bump). No new migration folder was added. Test-only modules are not bumped (validation obligation 1).
