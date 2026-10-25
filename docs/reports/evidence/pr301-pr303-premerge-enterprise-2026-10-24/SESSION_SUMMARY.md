# Pre-merge Enterprise run, 2026-10-24

PR #301 and PR #303 were tested as they would run after a clean merge into current `Staging`, on the admitted Enterprise fixture `odoo_test_tpl_ee_c9e8a81f52f23680`. The combined tree was tested in the same session. No product code was changed. The local merge commits were not pushed. The later close of the assessment gaps is `GAP_CLOSURE.md`.

## Trees

| Tree | Commit | Tree SHA | GitHub head it came from |
|---|---|---|---|
| M301 | `b91937fb26020d097391cb142fce35e9c8434cd2` | `187b69b8fbaa0add60089e5e4b783cbc85d853fa` | #301 `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79` merged onto `Staging` `2a3b9cda9b127c284d12f98bf35ab0344a500d10` |
| M303 | `190c497bdea1362cad87e231c713efdcd25240d4` | `916255549699a0d5395581a9c763d8fb11360959` | #303 head. That head already contains `Staging`, so the merge tree equals the head. |
| BOTH | `1606626ee845e1eb64a525cb0c39fc8140de9db3` | `203986bc9553955ee86e7c683ae4a563b900dafb` | M301 merged with M303. Clean. Every file changed by either PR is present. |

#301's tip does not contain `Staging`. The only difference between the tip and M301 is the already-merged PR #300 Linda BRS documents. Worktrees: `wt-premerge-301`, `wt-premerge-303`, `wt-premerge-both`. Each receipt has `dirty: false`.

The only path both PRs change is `plasticos_transaction/__manifest__.py`. Both sides are the same blob, version `19.0.2.3.40`. Git produced a clean union. That does not by itself prove the two transaction code changes work together; the BOTH module run is that proof for the tests that executed.

## Fixture

Template comment stayed `state=ready`, parity `ee`, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`. `scripts/test_env.sh status` was run from the M301 worktree. The Docker image ID after that status was `sha256:aa4c420fe3be5f68e8747f835016e82414b9b3a8ef0aedf5d06c10ad7bb21382`, created 2026-10-17. The fixture fingerprint did not change, so the run continued. Clones were dropped after the receipts were copied. None of `odoo_test_m301*`, `odoo_test_m303*`, or `odoo_test_both*` remained.

## Pure pytest

| Tree | Files | Result |
|---|---|---|
| M301 | `tests/test_erp_native_orders.py`, `tests/test_erp_native_document_guard.py`, `tests/test_erp_mapping_status.py` | 48 passed |
| M303 | `tests/test_odoo_test_discovery.py` | 4 passed |
| BOTH | the two native-order files plus `tests/test_odoo_test_discovery.py` | 40 passed |

`tests/test_erp_source_layer.py::test_trade_date_is_the_earliest_ledger_date` was not in that first selection. The gap close below ran it, with the two due-date helpers, and saved the verbose logs.

## Enterprise module runs

All five used `make test-module` on a fresh clone. The runner upgraded the 25-module PlasticOS roster and limited tests to the named module. Receipts are under `runtime/`.

| Lane | Module | Tests in the Odoo summary | Failed | Errors | Exit |
|---|---|---|---|---|---|
| M301 | `plasticos_transaction` | 47 | 0 | 0 | 0 |
| M303 | `plasticos_transaction` | 66 | 0 | 0 | 0 |
| BOTH | `plasticos_transaction` | 68 | 0 | 0 | 0 |
| M303 | `plasticos_partner_import` | 27 | 0 | 0 | 0 |
| BOTH | `plasticos_documents` | 23 | 0 | 0 | 0 |

Methods that the log shows starting, in suites that then reported zero failures:

- M301 and BOTH: `TestErpWorksheetImport.test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event`, `test_delivered_basis_sets_no_incoterm_and_undated_invoice_stays_undated`, `test_historical_documents_stay_draft_with_no_settlement_entries`
- M303 and BOTH: `TestSaleConfirmTransactionCreation.test_confirm_creates_transaction`, and the historical-draft worksheet test
- BOTH documents: `TestAccountMoveComplianceGate.test_invoice_rule_without_document_blocks_invoice`, `test_compliance_check_blocks_invoice_when_docs_missing`, `test_compliance_service_scopes_rules_by_purpose`, `test_close_only_rule_does_not_block_invoice`

M303's transaction run did not start the two #301 bill/incoterm methods. Those methods are not on that tree.

`TestErpWorksheetImport` did not fail setup on `plasticos_accounting.account_40050_sales_income`. The Community setup error from the #303 handoff did not reproduce on this fixture.

## What this does not prove

No restored SQL Server import and no live VanillaSoft sync ran. Module tests roll back. The result is `COMBINED_RUNTIME_PASS` for the modules above, and `END_TO_END_NOT_PROVEN` for a real import replay.

The seven Community failures in claims, offer, and ACL were not executed. `PR303_MERGE_READY` stays no. Logistics tests were not selected. #303's logistics files are in M303 and BOTH, and the roster upgrade loads `plasticos_logistics`. That is not a logistics acceptance.

The gap close is in `GAP_CLOSURE.md`. It records the exact #301 head receipt, the one-clone transaction-plus-documents run, the pure due-date and trade-date logs, and a shell probe of the compliance auto-post transition. The seven Community claim, offer, and ACL failures, and a restored SQL Server plus VanillaSoft replay, stay unrun on purpose.
