# Gap close, 2026-10-24

This file answers `PR301_PR303_Enterprise_Evidence_Assessment_2026-10-24.json`. The fixture stayed the admitted template `odoo_test_tpl_ee_c9e8a81f52f23680`, state ready, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`. The comment is identical in `runtime/fixture-before-gap-close.txt` and `runtime/fixture-after-gap-close.txt`. The clones created for this close were dropped. No product code was edited. Nothing was pushed.

## Closed

### F-002 — #301 GitHub head

`make test-module m=plasticos_transaction` on a wired worktree at `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79`.

Receipt `runtime/pr301-head-transaction/odoo_test_pr301head_tx_10242020.test-receipt.json`:

| Field | Value |
|---|---|
| head | `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79` |
| dirty | false |
| template | `odoo_test_tpl_ee_c9e8a81f52f23680` |
| fingerprint | `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30` |
| tests | 47 failed 0 errors 0, exit 0 |

The log starts `test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event` and `test_delivered_basis_sets_no_incoterm_and_undated_invoice_stays_undated`. Odoo summary: `0 failed, 0 error(s) of 47 tests`.

Against M301 `b91937fb`, the tip differs by the PR #300 Linda BRS documents, `AGENTS.md`, and `tests/contracts/test_logistics_brs_registry.py`. No `plasticos_transaction` or `plasticos_partner_import` Python or XML differs. The transaction manifest blob is `8502971f127a0ab252c361aba0b03e24ca7cd9e6` on the tip, on M301, and on #303.

### F-006 — due date and trade date

Verbose pytest, 3 passed, exit 0, on M301 and on BOTH. Logs: `pure/m301/due-date-and-trade-date.txt`, `pure/both/due-date-and-trade-date.txt`.

- `test_matched_term_applies_only_to_a_dated_bill` asserts an undated bill (`invoice_date` empty, `due_date` `2022-04-20`, matched term id 7) returns `invoice_payment_term_id` false and `invoice_date_due` equal to that header date.
- `test_unmatched_term_uses_the_header_due_date_and_clears_the_default_term` passed beside it.
- `test_trade_date_is_the_earliest_ledger_date` passed against the frozen extract. It requires at least 7,000 dated headers and checks the earliest `GPLedger.TradeDt`.

The ORM method `test_delivered_basis_sets_no_incoterm_and_undated_invoice_stays_undated` passed on M301, on the #301 tip, and on BOTH. It asserts `purchase.date_approve` is false when every `TradeDt` is missing, records the anomaly `date_approve not set (no GPLedger trade date)`, and leaves the customer invoice undated.

`test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event` passed on those same runs. It asserts a dated unmatched bill keeps `invoice_date_due` `2022-03-20` and clears the partner's default term. It does not build an undated vendor bill. That `account.move` assertion is the remaining slice of 301-D, and it is rank 3 of the approval queue.

### F-010 — one clone for both modules

`make test-module m=plasticos_transaction,plasticos_documents` on BOTH `1606626ee845e1eb64a525cb0c39fc8140de9db3`.

Receipt `runtime/both-transaction-documents/odoo_test_both_txdocs_10242020.test-receipt.json`: dirty false, same template and fingerprint, scope `plasticos_transaction,plasticos_documents`, 91 tests, 0 failed, 0 errors, exit 0. The log runs the transaction suite and then `plasticos_documents` on that same database. 68 plus 23 is 91.

### F-005 — auto-post transition

No registered test calls `_auto_post_pending_invoices`. A shell on a disposable BOTH clone did. The script is `runtime/both-autopost-probe/probe.py`. It rolls back. The clone was dropped.

One existing `plasticos.transaction` document rule was deactivated so the probe rule was the only one. A transaction was created missing that document, with a draft customer invoice and, in the third run, a draft vendor bill. Neither move had `invoice_origin`.

| Run | Before | After a verified document | Result |
|---|---|---|---|
| `probe-output-2.txt` | compliance `missing`, invoice `draft` | compliance `compliant`, invoice `posted`, missing empty | The transition called `action_post`. The purpose gate did not run, because the invoice has no sale origin. |
| `probe-output-3.txt` | both moves `draft`, compliance `missing` | compliance `compliant`, both moves still `draft` | `action_post` raised `The Bill/Refund date is required to validate this document.` |

The invoice-block tests still pass and still show that a missing `required_for_invoice` document blocks `action_post` when the invoice origin is a sale order. They do not stand in front of a linked draft that has no origin. Rank 4 of the queue is that decision.

### F-007 — second deploy at the same version

Git merge of these two SHAs is clean. Staging's `plasticos_transaction` is `19.0.2.3.39` (`c3b77c0412ef51410a3a63d9a2dbcfae98300ba6`). Both PR heads and BOTH are `19.0.2.3.40` (`8502971f127a0ab252c361aba0b03e24ca7cd9e6`).

Odoo upgrades a module when the manifest version is newer than the installed version. After the first of these PRs deploys, the installed version is `19.0.2.3.40`. The second PR's manifest is that same blob, so the module is not upgraded again.

#301's transaction change is `native_document_import.py`. #303's is `account_move_inherit.py` and `transaction.py`. Whichever lands second does not load unless that branch bumps `plasticos_transaction` above `19.0.2.3.40`. #303's other modules are not in #301, so their own version bumps still apply. Rank 5 of the queue replaces the earlier "no edit required" line.

### F-008 — filestore traceback

`test_confirm_creates_transaction` logs `FileNotFoundError` for filestore object `1f/1fd21bb695b92439ea61c76efc32672373066a1f`, then `filestore gc 1 checked, 1 removed`, then the next test starts. The same hash appears on the earlier BOTH transaction log and on the one-clone log. The suite result stays 0 failed.

`scripts/test_env.sh` `clear_filestore` removes `/var/lib/odoo/.local/share/Odoo/filestore/<clone>` so a reused clone name cannot keep an old filestore. The cloned database still has the template's attachment row. The miss is that row. It is not a failure of either PR.

### F-009 — logs and fixture

Pure verbose logs are under `pure/m301/` and `pure/both/`. Fixture comment before and after this close are `runtime/fixture-before-gap-close.txt` and `runtime/fixture-after-gap-close.txt`. Image `odoo19-odoo:latest` is `76a97c1a274a`, created 2026-10-17. Drop of `odoo_test_pr301head_tx_10242020`, `odoo_test_both_txdocs_10242020`, and `odoo_test_both_autopost_10242020` each printed `dropped`. The after query lists none of those names.

### F-001 and F-003

F-001 counted 231 test invocations across five runs. Those are module summaries, not 231 unique behaviors. The new runs add 47 on the #301 tip and 91 on the combined clone; the 91 includes the 68 transaction tests and the 23 document tests that previously ran on two clones.

F-003 called the BOTH run early against the old locked gate. The v2.4.0 contract runs BOTH in this campaign. The one-clone receipt is that gate's single invocation.

## Left open on purpose

F-004. The seven Community claim, offer, and ACL failures were not added to this close. Rank 2 of the queue still asks for a separate authorization before those modules are run.

A restored SQL Server import and a live VanillaSoft sync were not run. `END_TO_END_NOT_PROVEN` stands.
