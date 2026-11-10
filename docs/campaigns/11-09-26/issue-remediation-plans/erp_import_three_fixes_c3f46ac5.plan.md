---
name: ERP import three fixes
overview: "Implementation plan for #307, #354, and #353. #307 is an independent literal-XMLID correction. #354 and #353 stay blocked until restored-SQL evidence and an operator rule exist. This plan is published as its own pull request into Staging. No issue code in this revision."
todos:
  - id: fix-307
    content: "After separate implementation authorization, share one literal-prefix classifier and prove operational vs historical posting with Odoo ORM tests. Do not wait on #354 or #353."
    status: pending
  - id: fix-354
    content: "BLOCKED. Stop until the operator approves the v10 Amount/Price and UoM rule and a live restored-SQL census confirms the zero-weight lines. Then realize representable lines and quarantine every unpriceable purchase-total payable without a partial bill."
    status: pending
  - id: fix-353
    content: "BLOCKED. Stop until restored SQL proves ReverseBatchNo, the operator approves the pairing rule, and an Odoo 19 test proves a guard-safe link. Do not write reversed_entry_id on a marked historical move."
    status: pending
  - id: publish-plan-pr2
    content: "Publish this plan alone as an independent pull request into Staging. Do not stack it on another plan branch."
    status: pending
isProject: false
---

# ERP import plan for [#307](https://github.com/cryptoxdog/IB-Odoo_19/issues/307), [#354](https://github.com/cryptoxdog/IB-Odoo_19/issues/354), and [#353](https://github.com/cryptoxdog/IB-Odoo_19/issues/353)

This document is the implementation plan. It is not implementation authority. No source file, test, manifest, SQL extract, or import runs from this revision. [#182](https://github.com/cryptoxdog/IB-Odoo_19/issues/182), [#183](https://github.com/cryptoxdog/IB-Odoo_19/issues/183), [#217](https://github.com/cryptoxdog/IB-Odoo_19/issues/217), and [#299](https://github.com/cryptoxdog/IB-Odoo_19/issues/299) stay outside it.

Review pin `b5b6056f01639212e722ccdec5b964b36deee9f5` and any earlier dirty-checkout or open-PR description are historical. Re-fetch `origin/Staging`, module versions, and the open PR set immediately before any later implementation. Do not treat the frozen 2026-08-07 grid extract as live evidence.

## Publication

The operator directed this plan to be an independent pull request into `Staging`. It is not stacked on the #217/#182 plan branch. PR 1 being unpublished does not block this document.

Tracked copy: `docs/campaigns/2026-11-08/issue-remediation-plans/erp_import_three_fixes_c3f46ac5.plan.md`. The Cursor plans store is not the committed path.

Publication uses a clean worktree from verified `origin/Staging`. The operator checkout is not switched, stashed, reset, or cleaned. The commit stages this one file. Unrestricted `make commit` is not used. `make pr` targets `Staging` and does not pass `base=` to another branch. The body comes from `.github/pull_request_template.md` through `scripts/build_pr_body.py`, with Summary, Changes, and Test plan, and without a changed-file manifest. No merge and no issue close on the PR URL. This pull request does not authorize the issue fixes.

## Three units

Publish and implement these as separate units when their gates differ. Do not hold #307 for a missing #354 or #353 decision. Do not merge a unit because its PR exists. A PR URL does not close an issue. Closure waits until that unit is merged and its own acceptance proof is recorded.

| Unit | State | May start when |
|---|---|---|
| #307 | Ready as a plan. Not authorized to code. | A separate implementation authorization names #307. No source-database decision. |
| #354 | Blocked | Operator-approved v10 quantity and UoM rule, plus a live restored-SQL census. |
| #353 | Blocked | Restored-SQL census, operator-approved pairing rule, and an Odoo 19 test of a guard-safe link. |

Each unit gets its own clean worktree from the verified base of that unit. A dirty checkout is not switched onto the implementation branch. Do not stash, pop, force-switch, reset, or clean. The worktree must show zero unrelated modifications before the first edit. Stage explicit paths only, and review the staged diff against that unit's allowlist. Unrestricted `make commit` is forbidden: the reviewed target stages tracked and untracked changes beyond the intended file. `make pr` runs only after that unit's tests and the publisher gate, with smoke not skipped.

Version strings are read from the manifests at implementation time. Bump only a module whose runtime code actually changes in that unit, by one patch past the version then on the branch. Do not reuse `19.0.2.3.59` or `19.0.2.10.36` as if they were still current. A test-only edit does not bump `plasticos_documents`.

## Stop gates

Stop the affected unit, and do not fill the gap with a guess, when any of these is true:

- The operator rule for quantity, UoM, or a proven reversal is absent.
- The restored SQL Server census is unavailable, or it contradicts the assumption written here.
- The UoM for a zero-weight line is unresolved. Do not read `WKSDetail.Units` as packages and do not invent `Each`.
- More than one payable, vendor, or document type could be the original, and the operator rule does not pick one.
- The only candidate link mechanism is an ordinary `write` of `reversed_entry_id` after the historical XMLID exists, a `sudo()` write, or a user-settable context flag.
- The Odoo 19 runtime test that would prove the unit is missing, or a replay would change an archived `account.move`.
- Payable reconciliation would close only by relabeling an amount or by omitting a `PayableID`.

## #307 Literal XMLID classifier

[`plasticos.transaction._historical_erp_moves`](plasticos_transaction/models/transaction.py) searches `ir.model.data` with `=like` on `legacy_erp_outinv_%`, `legacy_erp_ininv_%`, and `legacy_erp_ledger_%`. SQL `LIKE` treats `_` as one character, and this method does not then apply `startswith`. [`account.move._historical_source_ids`](plasticos_transaction/models/account_move_inherit.py) uses the same `=like` domain and then keeps a row only when `name.startswith` one of those three prefixes. `action_post`, `write`, and `button_cancel` use that filtered set. `_auto_post_pending_invoices` subtracts `_historical_erp_moves` and then calls `action_post`. Compliance does not call `_auto_post_pending_invoices`. Do not add a compliance-triggered post.

Smallest change: one read-only classifier. Delete the three `=like` clauses from `_historical_source_ids`. Keep `module = plasticos_transaction`, `model = account.move`, and `res_id in self.ids`, then `startswith` on one module-level tuple:

`HISTORICAL_ERP_MOVE_PREFIXES = ("legacy_erp_outinv_", "legacy_erp_ininv_", "legacy_erp_ledger_")`

Keep the existing `sudo()` and its comment on that search. Do not add another `sudo()`. `_historical_erp_moves` returns the empty recordset for empty input, otherwise `moves.browse(list(moves._historical_source_ids()))`. No importer identity change and no posting-policy change.

Required Odoo 19 Enterprise ORM results, in [`plasticos_documents/tests/test_account_move_transaction_link.py`](plasticos_documents/tests/test_account_move_transaction_link.py), beside the tests already there:

- `legacy_erp_outinv_`, `legacy_erp_ininv_`, and `legacy_erp_ledger_` are classified. The ledger case stays in `test_ledger_prefix_is_classified_without_a_transaction_link`, including the wrong module `plasticos_accounting` and the same name on `sale.order`.
- `legacyXerpXoutinvX123` is not classified. On a draft `out_invoice` built like `test_lookalike_origin_stays_draft_until_explicit_post` (`origin="54839"`, `invoice_date="2022-04-01"`) and linked as `customer_invoice_id`, `_auto_post_pending_invoices()` posts it. Do not call `_satisfy` as the proof.
- A real `legacy_erp_outinv_` draft is excluded from that call and stays draft. Explicit `action_post()` still raises `Archived ERP invoices, vendor bills and credits cannot be posted.`
- A mixed set posts the operational draft and leaves the historical draft unposted.
- Existing compliance tests still show a verified document leaves drafts unposted. Do not change those assertions.

The implementer records the actual test command and the receipt. This plan does not claim that `make pr` or an Odoo run already happened. `plasticos_documents` is not version-bumped for a test-only edit. `plasticos_transaction` is bumped only if its Python changes in the #307 unit.

## #354 Zero-weight amounts

Blocked until both prerequisites exist. Do not start the code from the notes below.

1. Operator-approved v10 rule: when `Amount / Price` is a valid commercial quantity, which source UoM is permitted, and what a blank UoM means. `WKSDetail.Units` is not reinterpreted. A missing or zero price does not become quantity 1.
2. Live restored-SQL census of zero-weight, nonzero-amount worksheet lines, with identity and amount totals and the sale-versus-purchase split. A prior workbook claim of two sale lines and fourteen purchase lines is a clue, not a count.

Weighted `SWeight` / `PWeight` behavior stays, including short-ton conversion at 2,000 lb in [`native_quantity`](plasticos_partner_import/erp/native_orders.py), existing rate precision, and the customer-invoice rule that a negative command total becomes `out_refund` with absolute prices. Only the zero-weight, nonzero-amount case gains an `Amount / Price` branch, and only after the operator rule says that case is valid.

[`purchase_bill_lines`](plasticos_partner_import/erp/native_orders.py) already uses `amount / price` for a vendor-bill material line and then stores `abs(quantity)` and `abs(amount) / abs(quantity)`, because the credit document is `in_refund`. Keep that absolute convention. Do not edit [`tests/production-rehearsal/fidelity.py`](tests/production-rehearsal/fidelity.py).

One pure function in `native_orders.py`, called from the existing line paths. No second import path. It classifies each line. Nonzero weight returns that weight and the current `unit_price` result. Zero weight, nonzero amount, and nonzero price returns positive `abs(amount / price)` and signed `amount / quantity`, so the line total equals the source amount. Zero weight and zero amount is skipped with no anomaly. Zero weight, nonzero amount, and missing or zero price is unrealizable. Parse with the existing numeric helpers before any anomaly text. Do not format a raw source string as a number. The anomaly keeps the source detail id and the parsed amount.

[`_line_terms`](plasticos_transaction/models/native_document_import.py) is the caller for sale lines, purchase lines, and [`_customer_invoice`](plasticos_transaction/models/native_document_import.py). Today the invoice does `if not weight: continue` and drops a unit-priced line with no anomaly. A representable line must be on the document, and the document total for those lines must equal the source amount (absolute on `out_refund` when the existing negative-total rule applies). An unrealizable line is not a silent `continue`: it is an exception that carries the detail id and the amount. A zero-quantity sale or purchase upsert is not how a nonzero amount is stored. Do not unlink an existing line on replay.

Vendor side, before `_move()`:

- A payable that is not the worksheet purchase total keeps the one-unit lump at `abs(amount)`. Freight `50200` keeps quantity 1 at `abs(amount)`. Do not change those economics.
- A purchase-total payable with at least one priced line and any other nonzero unpriced line does not become a partial bill. Quarantine the whole payable. A partial archival bill is allowed only if the operator approves one disposition that names every source amount, reconciles the payable total, and does not label the partial document as the source total. That approval is not assumed.
- A purchase-total payable with no representable line does not become a bill and does not use quantity 1. One quarantine, one identity, the source amount.
- [`_vendor_bills`](plasticos_transaction/models/native_document_import.py) must not create the move, and must not append `billed_payables`, when the line decision is empty or is an unapproved partial set.
- The quarantined payable is not also counted as freight or as other expense. The Payables census still closes, with billed and quarantined identities and amounts each explicit. If the only way to close it is to relabel the row, stop.

Pure tests in [`tests/test_erp_native_orders.py`](tests/test_erp_native_orders.py): zero and negative weighted amounts, valid and invalid price, blank UoM, short tons, the unmatched charge lump, and freight quantity 1. The existing short-ton bill assertion stays.

Odoo 19 ORM tests in [`plasticos_transaction/tests/test_erp_worksheet_import.py`](plasticos_transaction/tests/test_erp_worksheet_import.py): invoice and bill totals for representable unit-priced lines, a mixed priced and unpriced worksheet, an all-unpriced worksheet, a zero amount, refunds and credits, no fabricated line, and a replay that does not change an archived document. Update an old assertion only when it encoded the silent drop. Do not loosen a weighted-line assertion.

## #353 Vendor reversals

Blocked. Do not project the column, do not mark it `VERIFIED`, and do not set `reversed_entry_id` from the notes below until the stop gates clear.

Restored SQL Server has to show `dbo.PayablesBatch.ReverseBatchNo` type, nulls, cardinality, and that the value is a batch reference; the relationship of `ReversedFxAmt`; source order; and the unmatched and ambiguous cases. Inspect at least batches `107184` and `107200` and worksheet `54839`. The frozen extract is a clue. The operator approves what a proven reversal is. An opposite-signed amount is not proof and is not a silent fallback.

`Payables.ReverseBatchNo` and `GPLedger.ReverseBatchNo` stay unmapped. `diagnostics/q4_columns.csv`, `bulk/PayablesBatch.csv`, and [`source_index.py`](plasticos_partner_import/erp/source_index.py) are read-only evidence. Do not patch them so a claim will pass.

Only after that approval, append `ReverseBatchNo` as the last select item of [`25_payablesbatch.sql`](plasticos_partner_import/erp_extracted_data/25_payablesbatch.sql), after `ReversedFxAmt`, with no `RTRIM` and no `CONVERT`. The reader already stringifies non-null cells and keeps SQL `NULL` as `None`. Then update the `PayablesBatch` disposition in [`mapping_status.py`](plasticos_partner_import/erp/mapping_status.py) and the enumerated expectations in [`tests/test_erp_source_layer.py`](tests/test_erp_source_layer.py) and [`tests/test_erp_mapping_status.py`](tests/test_erp_mapping_status.py): `PAYABLES_BATCH_COLUMNS`, the positional reader row, `PAYABLES_BATCH_PROJECTED`, and the verified-field assertion. `APBatchNo` and `PrePay` stay the first two columns. Do not claim `VERIFIED` before the evidence and the written target are both true. The SQL comment that says no Odoo field is written from header columns after `PrePay` changes only to name this one approved target.

The pairing function must receive the credit's own `PayableID` plus the vendor, worksheet, and source facts required to reject a bad match. A signature of `(batch_no, header, payables_by_batch)` cannot do that. Accept one original only when all of these hold: a distinct payable id, the original document is an `in_invoice` rather than another credit, the same vendor, and the source-proven reverse batch. Report, and do not link, a missing original, a duplicated batch header, multiple payables, a cross-vendor pair, a self reference, a same-sign amount, a prepay or otherwise excluded source row, and a batch value that is blank, zero, or the credit's own batch. Positive bills are not candidates and get no anomaly. Freight credits are candidates only under the same rule. The anomaly keeps the credit `PayableID` and the reason.

Hard contradiction: [`account.move.write`](plasticos_transaction/models/account_move_inherit.py) refuses `reversed_entry_id` when `_historical_source_ids()` is non-empty, with `Archived ERP source documents are read-only and cannot be posted or rewritten.` [`_move`](plasticos_transaction/models/native_document_import.py) writes the XMLID immediately after create, and on replay returns the existing move unchanged. A vendor credit's xmlid is `legacy_erp_ininv_{token}`. A later `credit.write({"reversed_entry_id": ...})` hits that guard, including a credit created earlier in the same run. Do not call that write safe because the run has not finished. Do not `sudo()` it. Do not add a user-settable context flag.

Prefer the relation on the create values when the original move already exists and the pairing is proven. If import order requires a deferred link, the plan for that mechanism is not this document's prescription. It has to be an explicit server-side invariant, reviewed on its own, that cannot update an older or replayed move, that names the fields and identity markers present at the write, and that leaves the normal archive guard intact for every other caller. If Odoo 19 ORM tests do not demonstrate it, #353 stays blocked and is not implemented.

`realize()` commits every 200 worksheets. A credit can be committed before its original exists. Do not emit `missing original` before the run's final resolution point. Do not keep the pending pair only in memory with no approved recovery: a crash must leave a deterministic unresolved anomaly, not a fabricated link and not a mutated historical document. Define that timing, the atomicity of the link relative to the commit, and what a rerun and a partial import do before any code is written. A rerun does not write an existing move.

ORM tests, when the unit is unblocked: one confirmed reversal, ambiguous and multiple reversals, cross-worksheet, cross-vendor, duplicate and self reference, a positive bill, a credit imported before its original, a credit on the other side of the 200-worksheet commit, restart and replay, an ordinary user whose `write` of `reversed_entry_id` on a marked historical draft still raises, no privileged bypass, and both the original and the credit remaining unposted drafts.

## Future implementation allowlist

These paths may be edited only after a separate authorization and only in a unit whose prerequisites passed. Listing them authorizes nothing now.

| Issue | File | Allowed change |
|---|---|---|
| #307 | `plasticos_transaction/models/transaction.py` | Shared literal-prefix move classification, no altered auto-post policy |
| #307/#353 | `plasticos_transaction/models/account_move_inherit.py` | #307 literal classifier; #353 guard-safe link protection only if essential and separately reviewed |
| #354/#353 | `plasticos_transaction/models/native_document_import.py` | Supported line-price and quarantine flow; proven vendor-credit relation and commit/replay accounting |
| #307/#354/#353 | `plasticos_transaction/__manifest__.py` | Minimal current-version increment for actual module code changes |
| #354/#353 | `plasticos_transaction/tests/test_erp_worksheet_import.py` | Odoo ORM totals, quarantine, reversal, replay and historical invariants |
| #354/#353 | `plasticos_partner_import/erp/native_orders.py` | Pure commercial-quantity and source-proven credit pairing functions |
| #353 | `plasticos_partner_import/erp/mapping_status.py` | Disposition of exactly newly verified `ReverseBatchNo` projection |
| #353 | `plasticos_partner_import/erp_extracted_data/25_payablesbatch.sql` | Project verified `ReverseBatchNo` only |
| #354/#353 | `plasticos_partner_import/__manifest__.py` | Minimal current-version increment for actual module code changes |
| #307 | `plasticos_documents/tests/test_account_move_transaction_link.py` | Explicit vs auto-post negative/positive classifier regression |
| #354/#353 | `tests/test_erp_native_orders.py` | Pure quantity/pairing tests including negative cases |
| #353 | `tests/test_erp_source_layer.py` | SQL column/reader tests only after source projection approved |
| #353 | `tests/test_erp_mapping_status.py` | Mapping status tests only after source projection approved |

Inside those files, do not edit unrelated methods, weaken or skip tests, add a global archive bypass, weaken a company or record rule, or change posting behavior beyond the unit.

## Prohibited implementation files

- `.env`, passwords, source dumps, credential stores, Odoo.sh Production configuration, user or tenant data, any broad database mutation, and all publication or deployment credentials.
- `.pre-commit-config.yaml`, `AGENTS.md`, `Makefile`, `scripts/git_push_with_pr.sh`, `scripts/pr_check_run.sh`, `scripts/pr_check_scope.py`, `.github/workflows/**`, `Dockerfile`, `docker-compose.yml`, `pipeline_v2.py`.
- `tests/production-rehearsal/**`, including `fidelity.py` and evidence or links. Do not modify the rehearsal kit to hide a failing import.
- `plasticos_security_base/**`, ACL CSVs, `security/record_rules.xml`, general security groups, XML views, cron, accounting fiscal or GL rules, payment and posting workflows, and generalized `sudo` policies.
- `plasticos_partner_import/erp/source_index.py`, `diagnostics/q4_columns.csv`, `bulk/PayablesBatch.csv`, `Payables.ReverseBatchNo`, `GPLedger.ReverseBatchNo`, and source extracts. Read-only evidence unless a later scope revision says otherwise. Do not patch a fixture so an unsupported claim will pass.
- No new model, module, or schema migration. No `pipeline_v2.py` edit. No expansion to #182, #183, #217, or #299. No blanket importer or mapping refactor. No unauthorized archival `account.move` write or replay repair.

## Proof required before an implementation PR

#307: the ORM classifier cases above, plus unchanged manual post of an operational invoice and unchanged archive refusal. Record the command and the receipt.

#354: the signed quantity and UoM rule, the restored-SQL census with identity and amount totals, the pure tests, and an Odoo ORM run that reconciles invoice and bill economics including every unpriceable exception.

#353: the source census, the approved pairing rule, the guard-safe link demonstrated in ORM tests, no cross-boundary or replay mutation, every ambiguous row reported, and link or refusal evidence. Both documents stay unposted drafts.

The local pure Python suite is run on its own. The publisher does not replace it. `make pr` for an implementation unit does not skip smoke. A local smoke is not an Odoo.sh staging proof and is not production sign-off. No issue is closed from a PR URL.

Operator questions that block a unit, and that this plan does not answer:

- #354: the approved `Amount / Price` rule, the permitted UoM, and whether a mixed priced and unpriced purchase-total payable is quarantined as a whole.
- #353: what `ReverseBatchNo` means on the restored database, what a proven reversal is, and which guard-safe mechanism may set the link when the original is not yet created.

## Final checklist

- [ ] Revalidated Staging head, PR states, worktree safety and current module versions.
- [x] #307 can proceed independently; #354 and #353 are separately blocked until source/operator evidence exists.
- [ ] One literal-prefix classifier preserves historical/operational posting behavior, proven by ORM tests.
- [ ] #354 operator-approved `Amount / Price`, units and SQL counts exist; `WKSDetail.Units` is not reinterpreted.
- [ ] Unit-priced sale and vendor lines realize the correct signed economics; no silently missing invoice line or amount.
- [ ] Every unpriceable purchase-total payable, including mixed representable/unrepresentable lines, gets an honest, amount-complete bill-or-quarantine disposition.
- [ ] `_vendor_bills()` explicitly blocks creation of empty or misleadingly partial bill line sets.
- [ ] #353 live `ReverseBatchNo` semantics, source projection, mapping status and operator approval are established before use.
- [ ] Vendor pairing verifies credit's own PayableID, original bill type/vendor, uniqueness and cross-worksheet/source integrity.
- [ ] Historical `reversed_entry_id` write guard is respected; no deferred post-marker write is assumed safe; any initial-only mechanism is proved in an Odoo 19 runtime.
- [ ] Commit-window, crash/replay, unresolved credit anomaly, no posting/payment and archival immutability regressions are specified.
- [x] Exact future implementation allowlist and prohibited file list are present, with no broad cleanup.
- [x] No unrestricted `make commit`. This plan is an independent pull request into Staging, with no issue closure, merge, or production action.
- [x] Plan front matter and tasks match prerequisites, stop conditions, tests and independent issue gates.
- [ ] PLAN-ONLY PR: no issue code changes, no falsely claimed tests, no merges or issue mutations. Record the PR URL, open status, head SHA, and base `Staging`.
- [x] This pull request is not stacked. Its base is Staging.
- [ ] `make pr` into Staging completed, with the template-generated body and no changed-file manifest.
- [x] This pull request does not start issue remediation. #307, #354, and #353 stay open.
