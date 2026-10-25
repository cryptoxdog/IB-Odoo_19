# Historical auto-post guard — implementation report

Contract `ODOO-303-HISTORICAL-AUTOPOST-GUARD-001`. Local commit only. PR #303 was not updated. Nothing was pushed, merged, or deployed.

| Item | Value |
|---|---|
| Parent | `190c497bdea1362cad87e231c713efdcd25240d4` (PR #303 head) |
| Branch | `fix/historical-autopost-guard` |
| Commit | `23e5bf9ecd0246a7195f40a2a1a114541d7d8fdc` |
| Worktree | `/Users/ib-mac/IB-Odoo_19 (LOCAL)/wt-historical-autopost` |
| #301 | read-only `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79`, unchanged |
| #303 worktree | still `190c497bdea1362cad87e231c713efdcd25240d4`, porcelain empty |
| Manifest | `plasticos_transaction` remains `19.0.2.3.40`. The version collision is untouched. |

## Diff

Two files, 243 insertions.

- `plasticos_transaction/models/transaction.py` — `_auto_post_pending_invoices` (line 879) subtracts `_historical_erp_moves` (line 904) before `action_post`. One `ir.model.data` search: module `plasticos_transaction`, model `account.move`, `res_id` in the candidate ids, name `=like` `legacy_erp_outinv_%`, `legacy_erp_ininv_%`, or `legacy_erp_ledger_%`. An empty remainder does not call `action_post`. `_compute_compliance` is unchanged.
- `plasticos_documents/tests/test_account_move_transaction_link.py` — class `TestHistoricalAutopostGuard`.

No sudo, no context bypass, no new field, no marker write.

## Tests

Command, from the worktree, with `ODOO_ENTERPRISE_PATH` pointed at the admitted Enterprise checkout:

```text
make test-module m=plasticos_documents fresh=0
```

The runner upgrades the declared PlasticOS roster and executes `plasticos_documents` only. Fixture `odoo_test_tpl_ee_c9e8a81f52f23680`, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`. Clone `odoo_test_both_autopost_10242020`, dropped after the run.

| Run | Head | Dirty | Result |
|---|---|---|---|
| Frozen method, tests only | `190c497` | yes | 31 tests, 3 failed, 2 errors. `test_historical_markers_stay_draft_when_compliance_is_satisfied` raised `UserError: The Bill/Refund date is required to validate this document.` from `_auto_post_pending_invoices` → `action_post` → `_post`. |
| Committed guard | `23e5bf9ecd0246a7195f40a2a1a114541d7d8fdc` | no | 31 tests, 0 failed, 0 errors, exit 0 |

Receipt: `wt-historical-autopost/.l9/runtime/test-env/odoo_test_both_autopost_10242020.test-receipt.json`. The later green run replaced the frozen receipt in that same path. The frozen summary and the bill-date traceback were captured from that first run.

The other frozen failures were not product behavior. `test_ledger_prefix_is_classified_without_a_transaction_link` errored because `_historical_erp_moves` did not exist yet. Three posting tests left the invoice link unflushed, so the compliance recompute did not see it. `_satisfy` now flushes first, which matches a document arriving after the link is already stored. Those tests pass on the committed guard.

Ruff `0.16.0` check passed on both files. The worktree has no pre-commit hook install; the commit did not run the repo hook set.

## Requirement map

| Requirement | Where | Evidence |
|---|---|---|
| Historical invoice and undated bill stay draft; compliance becomes compliant; a later document write does not post them; `action_post` is not what posts them | `test_historical_markers_stay_draft_when_compliance_is_satisfied` | Frozen run raised the bill-date error, so `action_post` ran. Committed run passes, so that error is gone and both states stay `draft` while status is `compliant`. |
| `legacy_erp_ledger_` excluded if it is a candidate | `test_ledger_prefix_is_classified_without_a_transaction_link` | The method returns the `out_refund`. The import does not store that credit on `customer_invoice_id`, `vendor_bill_ids`, or `freight_bill_ids` (`test_worksheet_54839_keeps_credit_freight_costs_and_excludes_prepay` on this parent). The test does not invent that link. |
| Operational sale-origin invoice still posts | `test_operational_sale_origin_invoice_still_autoposts` | Pass |
| Mixed set posts only the unmarked move | `test_mixed_set_posts_only_the_unmarked_move` | Pass |
| Wrong prefix, wrong module, wrong model, worksheet-shaped origin do not block | `test_lookalike_origin_and_xmlid_do_not_block_autopost` and the classifier assertions in the ledger test | Pass |
| Direct post of a dated historical draft posts; undated bill still fails the core date check | `test_direct_post_of_a_historical_draft_uses_normal_accounting` | Pass |
| Marker does not skip the invoice-purpose gate | `test_historical_marker_does_not_bypass_the_invoice_purpose_gate` | Pass. Raises `Missing required documents for invoice posting.` |
| Operational undated bill rolls back and retries | `test_operational_undated_bill_rolls_back_and_retries` | Pass. Savepoint rolls the document and the compliance write back. After the date is set, the next document posts both moves. |

## Independent checklist

| Assertion | Result |
|---|---|
| Historical-only stays draft across `missing` → `compliant`, including an undated bill and a repeated document write | PASS |
| Same historical-only case fails on frozen `190c497` and passes on `23e5bf9e` | PASS |
| `legacy_erp_ledger_` classified by the method without a new relationship | PASS |
| Ledger move actually sitting on one of the three candidate fields and then excluded | NOT_RUN. The import does not put that credit on those fields. |
| Operational sale-origin invoice auto-posts | PASS |
| Mixed set: operational posts, historical stays draft | PASS |
| Unrelated xmlid, wrong module, wrong model, similar origin do not suppress posting | PASS |
| Direct `action_post` on a dated historical draft posts | PASS |
| Direct `action_post` on an undated bill raises the core date error and leaves it draft | PASS |
| Historical marker does not bypass `purpose="invoice"` | PASS |
| Operational undated bill: uncaught error rolls the transition back; dating it lets the next document post both | PASS |
| `plasticos_documents` module suite on the admitted Enterprise fixture, committed SHA, dirty false | PASS. 31 tests, 0 failed, 0 errors |
| Product diff limited to the authorized method plus the existing test file | PASS |
| #301 and #303 heads unchanged; no push | PASS |
| Manifest version collision, ACL unlink pass, seven claim/offer/ACL failures, due-date anomaly | NOT_RUN. Out of scope. |

## Left for the operator

Publication, merge, and the `plasticos_transaction` bump above `19.0.2.3.40` are separate decisions. This commit is not on PR #303.
