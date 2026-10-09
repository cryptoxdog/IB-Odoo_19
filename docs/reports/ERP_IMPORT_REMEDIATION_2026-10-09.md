# ERP Native Import Remediation — Evidence Report

Date: 2026-10-09 · Repo: `cryptoxdog/IB-Odoo_19` · Audit baseline: `9f4b25be` (`feat/erp-native-mapping`, PR #227)

Scope: the seven GAR-audit findings F1–F7 on the ERP → native SO/PO/invoice/bill → PlasticOS
transaction import, proven on a disposable Odoo 19 database. No production database was written.
Pipeline preserved: ERP SQL Server → source projections (`erp_extracted_data/*.sql`) → `SourceIndex`
→ existing ORM importer → native documents → transaction compilation. No second importer, no CSV
path, no new field on `plasticos.transaction`.

Evidence artifacts referenced below live in `docs/reports/evidence/erp-import-2026-10-09/`.

---

## 1. Branch and SHA

| Item | Value |
|---|---|
| Remediation branch | `fix/erp-import-remediation` (isolated worktree, based on `9f4b25be`) |
| Code commit | `4ef5e80` — `fix(import): remediate the ERP native import audit findings F1-F7` |
| Base | `Staging` |
| Also present on | `feat/erp-native-mapping` (`3f000dc` + `6b0111f`), mixed with unrelated UI work from a parallel session; the isolated branch carries the remediation alone |

## 2. F1–F7 closure matrix

| # | Finding | Authoritative source of the defect | Correction | Deterministic test | Runtime proof | Status |
|---|---|---|---|---|---|---|
| F1 | Import mutated global tax configuration | `native_document_import._clear_default_taxes` wrote product/company tax defaults | Removed; imported lines carry `tax_ids=[Command.clear()]`, `is_imported=True` | `test_import_leaves_tax_configuration_alone_and_imports_without_taxes` | 0 tax links on 19 458 imported order lines and 20 207 move lines (full run) | Closed |
| F2 | Fabricated settlement (payments / clearing entries) | `_settle_historical`, `_clearing_account`, retained-earnings lookup | Removed; documents created once and left draft; QuickBooks remains payment owner | `test_historical_documents_stay_draft_with_no_settlement_entries` | payments 0 · entries 0 · settlement lines 0 · equity lines 0 · full/partial reconcile 0 (full run) | Closed |
| F3 | `rule_purchase_order_all_documents` granted `[(1,'=',1)]` CRUD to `group_sale_salesman_all_leads` | `plasticos_security_base/security/record_rules.xml` | Rule deleted (file is `noupdate="0"`, upgrade removes it); own-records rule kept | `test_purchase_order_access.py` (4 tests: rule absent and no open-domain rule, rep own-only, all-leads not widened, accounting read-only) | Fresh DB installed from this branch: only multi-company, portal, and sales-rep own-records rules on `purchase.order` (`evidence/f3_rules.txt`); 4/4 tests pass (`evidence/runtime_tests_f3.txt`) | Closed |
| F4 | One worksheet ≠ one transaction; duplicate orders | `_upsert_order` created an order per worksheet; `action_confirm` compiled per order | Orders keyed on source `PONumber`, every worksheet appended to `origin`; `_compile_worksheet_transactions` creates one transaction per worksheet, skips existing; join `WKSDetail.SPO_ID/PPO_ID → PODetail.PO_ID → PO` | `test_two_worksheets_on_one_sale_order_…`, `…_across_commit_batches`, `test_worksheet_with_two_sale_orders_compiles_one_transaction` | 6 914 SOs / 7 022 POs, 407 SOs and 431 POs serve several worksheets, duplicate order names 0, duplicate identity markers 0, 7 688 transactions each named by its worksheet | Closed |
| F5 | Credits, freight bills, handling costs lost; prepay leaked | `_customer_invoice` ignored GPLedger adjustments; `_vendor_bills` dropped non-material GL | `_customer_adjustments` (approved A/S → `out_refund` with `reversed_entry_id`, debits via `debit_origin_id`); GL 50200 → freight bill on seeded `50200 Freight Cost`; GL 50300/50600 → `other_expenses`; `PrePay=1` batches skipped; `revenue_total` nets credit notes | `test_worksheet_54839_keeps_credit_freight_costs_and_excludes_prepay`, `test_worksheet_53797_nets_to_zero_revenue_and_negative_margin` | §8 below | Closed |
| F6 | Commission recipient substituted by current owner; no cutoff | `worksheet_commission` reassigned initials; no lock | `commission_slots` keeps raw `ReferrerNo` + amount per slot; recipient = slot carrying the amount; `_lock_historical_commission` locks amount, `paid` before 2026‑06‑01, `unpaid` on/after, from the source order date; two paid recipients → anomaly + chatter | `test_commission_recipient_amount_and_cutoff_per_slot` (0/1/2 slots, 2026‑05‑31 vs 06‑01, paid slot beats named-unpaid slot), `test_worksheet_commission_*` (pure python) | §10 below | Closed |
| F7 | No real-runtime proof; replay not deterministic | `_differs` flagged `Command.clear()` vs empty, date strings, float noise as changes; Odoo 19 confirm overwrote `date_order` | `_differs` normalised; `_prepare_confirmation_values` keeps source date under `import_mode`; product-cache `exists()` guard | `test_two_worksheets_on_one_sale_order_compile_two_transactions_and_replay_adds_nothing` (in-process replay: created 0, snapshot identical) | Full first run completed (§6); **full second run not completed** (§7) | **Partially proven — see §12** |

## 3. Files changed (commit `4ef5e80`, 18 files)

| Module | File | Purpose |
|---|---|---|
| `plasticos_transaction` | `models/native_document_import.py` | F1 F2 F4 F5 F6 F7 |
| | `models/sale_inherit.py` | F4 compile-per-worksheet, F6 lock/cutoff, `date_order` preserved |
| | `models/transaction.py` | F5 revenue nets `reversal_move_ids`; freight bills signed |
| | `tests/__init__.py`, `tests/test_erp_worksheet_import.py` | new — 11 runtime tests |
| | `__manifest__.py` | 19.0.2.3.18 → 19.0.2.3.24 |
| `plasticos_partner_import` | `erp/native_orders.py` | commission slots/recipients, ledger adjustment kinds, worksheet-origin helpers |
| | `erp_extracted_data/15_gpledger.sql` | `AdjApproved`, `AdjMemoNo`, `AdjDocTitle` projected |
| | `models/erp_import_service.py` | `_differs` normalisation |
| | `__manifest__.py` | 19.0.2.10.12 → 19.0.2.10.14 |
| `plasticos_security_base` | `security/record_rules.xml` | F3 rule removed |
| | `tests/__init__.py`, `tests/test_purchase_order_access.py` | new — 4 access tests |
| | `__manifest__.py` | 19.0.1.2.16 → 19.0.1.2.19 |
| `plasticos_accounting` | `data/accounts.xml` | `account_50200_freight_cost` seed |
| | `__manifest__.py` | 19.0.1.6.0 → 19.0.1.6.1 |
| repo tests | `tests/test_erp_native_orders.py`, `tests/test_phantom_enum_values.py` | pure-python tests; allowlist for `expense_direct_cost` and document-map keys |

No frozen ADR was rewritten. No contract field was invented. No ERP business semantics changed.

## 4. Test results

| Tier | Command / scope | Result |
|---|---|---|
| Pure python (repo) | `pytest tests/` on the working tree | 1 093 passed, 45 skipped |
| Pure python (branch subset) | `tests/test_erp_native_orders.py`, `test_phantom_enum_values.py`, `test_repo_dependency_integrity.py` | 67 passed |
| Odoo runtime (import) | `odoo --test-enable --test-tags /plasticos_transaction,/plasticos_security_base -u …` on fresh `erp_import_proof` (22:09 UTC) | **0 failed, 0 errors of 13 tests** (`evidence/runtime_tests.txt`) — note: this DB was mounted from the working checkout, where the F3 rule was still present, so the security tests in that run exercised the pre-fix rule |
| Odoo runtime (F3) | fresh `erp_f3_proof` installed from **this branch** (`-i plasticos_security_base`, 22:35 UTC), `--test-tags /plasticos_security_base` | **0 failed, 0 errors of 4 tests** (`evidence/runtime_tests_f3.txt`); DB dropped afterwards |
| Static gates | ruff check/format, BAN001, module wiring, circular deps, Odoo 19 XML, orphan refs, odoo patterns, audit-baseline | all pass on the branch |
| OdooLS (parse mode, this worktree) | files touched by the remediation | 1 finding fixed (test referenced a model from a dependent module); 4 remaining findings pre-exist at `9f4b25be` |

Three runtime-only faults were found and fixed by the runtime tier, none visible to pure-python tests: Odoo 19 `action_confirm` overwriting `date_order` with "now" (would have broken F6's cutoff and F7's replay); a duplicate-name user fixture; and the F3 access test, which had been committed still asserting the *old* all-documents rule and was corrected to assert its absence before publication.

## 5. SQL snapshot and target database identity

| Item | Value |
|---|---|
| Source | Restored ERP database on Microsoft SQL Server 2022 (RTM-CU27, 16.0.4295), local lab container, read directly via `pymssql` from the Odoo container (`host.docker.internal:1433`); credentials and database name supplied by environment only — never written to repo content or logs |
| Source row counts | BuySell 8 961 · PO 14 724 · PODetail 19 630 · WKSDetail 11 441 · GPLedger 8 353 · Payables 14 649 · PrepayLedger 41 · PayablesBatch `PrePay=1` batches 38 (`evidence/source_counts.txt`) |
| Target | `erp_import_proof` on PostgreSQL 15.18 (`odoo19-db-1`), created for this proof, Odoo 19 with enterprise addons path, 480 modules installed (`account_debit_note`, `l10n_us*`, all `plasticos_*`), no demo data |
| Pristine check before import | `res_partner` 29 (system only) · `sale_order` 0 · `account_move` 0 · `plasticos_transaction` 0 (`evidence/db_pristine.txt`) |
| Entry point | `plasticos_partner_import/scripts/import_erp_shell.py` via `odoo shell`, exactly the `make import-erp` contract (`ERP_TARGET_DB=erp_import_proof`, `ERP_SQL_*` env) |

## 6. First-run counts (full run, 21:03–22:02 UTC)

Summary (`evidence/run1_summary.json`): `records_seen 32 332 = created 25 694 + updated 2 115 + unchanged 2 091 + rejected 2 432`; `duplicates 0`; `final_status partial` (rejections are source-explained: inactive counterparties and unresolvable order references).

Identity markers written (`plasticos_transaction` module):

| Marker prefix | Model | Count |
|---|---|---|
| `legacy_erp_cp_` / `_address_` / `_contact_` | res.partner | 1 300 / 2 602 / 3 728 |
| `legacy_erp_so_` / `_sol_` | sale.order / line | 6 914 / 9 468 |
| `legacy_erp_po_` / `_pol_` | purchase.order / line | 7 022 / 9 990 |
| `legacy_erp_outinv_` | account.move (customer invoice) | 6 842 |
| `legacy_erp_ledger_` | account.move (credit/debit memo) | 176 |
| `legacy_erp_ininv_` | account.move (vendor bill / refund) | 13 189 |
| `legacy_erp_grade_` | product.product | 330 |

Documents: `out_invoice` 6 859 (32 260 188.36) · `out_refund` 159 (137 612.60; 147 linked by `reversed_entry_id`) · `in_invoice` 11 307 (27 410 253.90) · `in_refund` 1 882 (2 467 728.37) — **all draft**. Transactions 7 688 (closed 6 832 · cancelled 768 · active 88).

Settlement artifacts: payments 0 · misc entries 0 · settlement lines 0 · equity lines 0 · `account_full_reconcile` 0 · `account_partial_reconcile` 0. (203 zero-balance receivable lines on 0.00 invoices show Odoo's computed `reconciled=True`; no reconcile record exists.)

This run exposed one importer fault (`evidence/run1_log.txt`, one `ERROR`): a worksheet rejected for an inactive vendor rolled back the product it had just created, but `product_cache` kept the dead record, so the next worksheets with that grade failed on `purchase_order_line_product_id_fkey`. Nine grades, about 50 active-counterparty worksheets were lost this way. Fixed in `4ef5e80` (`_product` re-resolves a cached record that no longer exists) with `test_rejected_worksheet_does_not_poison_the_product_cache`.

## 7. Second-run (replay) diffs

**Not completed at full scale.** After the fix in §6, the proof DB was dropped and rebuilt (pristine check repeated), the 13 runtime tests passed on it, and the corrected first run was relaunched (18:10 local). That container was removed by activity outside this session at about 18:14 after 550 transactions / 468 sale orders had been committed, and the test environment is now being rebuilt. The second run therefore never started.

What *is* proven for replay:

- In-process replay in `test_two_worksheets_on_one_sale_order_compile_two_transactions_and_replay_adds_nothing`: second `realize()` over the same `SourceIndex` → `transactions created 0`, `transaction_lines created 0`, normalised snapshot of orders/lines/moves/transactions identical.
- `_differs` normalisation covers the three sources of false writes observed in the first run (x2many clear vs empty, date strings vs stored dates, float digits).
- `_upsert_order` on an already-confirmed order writes only when `origin` actually changes; `_compile_worksheet_transactions` skips any worksheet already compiled.

Required to close: rebuild `erp_import_proof` (`evidence/run_import.sh run1`, then `run2` with `ERP_REQUIRE_EMPTY=0`), run `evidence/snapshot.sql` + `evidence/dump.sql` after each, `diff run1_dump.txt run2_dump.txt` must be empty, and `created` must be 0 for every bucket in the second summary.

## 8. Worksheets 54839 and 53797 (first run, `evidence/run1_dump_excerpt.txt`)

**54839** — SO 14263 (origin `54839`, confirmed, `date_order` 2022‑02‑18 preserved), PO 7275 (draft RFQ, 2022‑02‑18).

| Item | Source | Odoo |
|---|---|---|
| Sold | SWeight 19 145 lb, SAmount 9 763.95 | SO line qty 19 145.00 @ 0.51 → invoice `legacy_erp_outinv_54839` 9 763.95 (draft) |
| Bought | PWeight 19 188 lb, PAmount 8 826.48 | PO line qty 19 188.00 @ 0.46 |
| Customer adjustment | GPLedger 5694, Source A / AdjType S / Approved Y, Sale −382.90, memo `CM 54839` | `legacy_erp_ledger_5694` `out_refund` 382.90, `reversed_entry_id` → the 54839 invoice, invoice_date 2022‑05‑12 |
| Vendor bills (GL 50100) | Payables 591398 +9 366.52 · 591476 −9 366.52 (`U-7275 / 54839`) · 594620 +8 826.48 | `in_invoice` 9 366.52 · `in_refund` 9 366.52 · `in_invoice` 8 826.48 — net 8 826.48 |
| Transaction | | revenue **9 381.05** (= 9 763.95 − 382.90) · cost 8 826.48 · margin 554.57 · commission slot 2 `TF` 55.4570 → locked 55.46, `paid`, user = the TF user |

**53797** — SO 13289 / PO 6240, 2021‑03‑04.

| Item | Source | Odoo |
|---|---|---|
| Sale | 200 × 10.00 = 2 000.00 | invoice `legacy_erp_outinv_53797` 2 000.00 |
| Credit | GPLedger 4670, A/S approved, Sale −2 000.00, `CM 53797` | `legacy_erp_ledger_4670` `out_refund` 2 000.00 linked to the invoice |
| Cost | Payables 562145, GL 50100, 2 000.00 | `in_invoice` 2 000.00 |
| Transaction | | revenue **0.00** · cost **2 000.00** · gross margin **−2 000.00** · slot 2 `IB` 0.00 → locked 0.00, `paid` |

Prepay: the 38 `PrePay=1` batches contain **0** Payables rows, and `PrepayLedger` is not a projected table, so none of its 41 rows can enter the pipeline; no `legacy_erp_ininv_` marker references a prepay batch. No QuickBooks payment is inferred anywhere (payments 0).

## 9. Multi-worksheet proof

- 407 sale orders and 431 purchase orders carry more than one worksheet on `origin` (e.g. `legacy_erp_so_11557` → origin `51666, 51667, 51680`, three transactions named 51666 / 51667 / 51680, one shared SO).
- Transactions per sale order: 6 506 × 1, 273 × 2, 63 × 3, … up to one SO serving 30 worksheets — all without a duplicate order name (0) or duplicate identity marker (0).
- Worksheet spanning two sale orders: 0 in this source; behaviour covered by `test_worksheet_with_two_sale_orders_compiles_one_transaction` (one transaction on the lowest-id SO, sibling noted in chatter, anomaly `worksheet carries 2 sale orders`).
- 66 transaction names are non-numeric (`52175R`, `51687-JCH`, …) — these are the source `BuySellNo` values verbatim, one transaction each.

## 10. Commission recipient and cutoff proof (first run)

| Worksheet | Source `OrderDt` | Slots | Odoo |
|---|---|---|---|
| 60545 | 2026‑05‑29 | slot 2 LR 0.00 | locked 0.00, **paid** |
| 60546 | 2026‑06‑01 | slot 2 AB 0.00 | locked 0.00, **unpaid** |
| 60548 | 2026‑06‑01 | slot 2 TF −0.04 | locked −0.04, unpaid, user TF |
| 60549 / 60550 | 2026‑06‑01 | TF 46.508 / 48.668 | locked 46.51 / 48.67, unpaid, user TF |
| 60555 | 2026‑06‑02 | AA 1 185.28 | locked 1 185.28, unpaid |
| 54839 / 58699 | 2022 / historic | TF 55.457 / 60.44 | paid, user TF |

Totals: 7 428 transactions `paid` + 260 `unpaid`, all `commission_locked`. 424 transactions have no `user_id` because the historical recipient (e.g. GS, RP, AA) has no Odoo user — nobody is substituted and each is reported (`commission recipient X has no user`). `plasticos_commission_payout` rows: 0 on the proof DB after 550 imported transactions (the importer has no payout code path; the first-run snapshot aborted before that query). No current-owner reassignment is applied anywhere in the recipient path.

## 11. Access-control and tax-isolation proof

- `purchase.order` rules on a DB installed from this branch (`evidence/f3_rules.txt`): `Purchase Order multi-company`, `Portal Purchase Orders`, `Plasticos: Purchase Order - Sales Rep Own Records` (`'|', ('user_id','=',user.id), ('create_uid','=',user.id)`). `rule_purchase_order_all_documents` absent; no rule with `(1, '=', 1)`; module at 19.0.1.2.19.
- Runtime tests (`evidence/runtime_tests_f3.txt`): rep A cannot read or write rep B's PO (AccessError); a rep also in `group_sale_salesman_all_leads` sees only own POs, cannot read another rep's PO, cannot unlink an unowned PO; accounting reads all and cannot write.
- Note for the operator: on a database that still carries the old rule (e.g. a DB upgraded from the working checkout before this change), `make update m=plasticos_security_base` removes it — the record is in a `noupdate="0"` file.
- Tax isolation: `product_taxes_rel` and `product_supplier_taxes_rel` for imported products 0; `account_move_line_account_tax_rel` 0 on imported moves; `account_tax_sale_order_line_rel` / `account_tax_purchase_order_line_rel` 0 on imported lines; company default tax settings untouched (asserted by `test_import_leaves_tax_configuration_alone_and_imports_without_taxes`).

## 12. Blockers, limitations, accepted behaviour

**Blocked**
- F7 full-scale second run (replay) — not executed; the corrected first run was killed externally at 550 transactions and the environment is being rebuilt. Steps to close are in §7. **F7 is not called complete.**
- Publication via `make pr` — not yet run; the Makefile and the Docker test environment are being changed outside this session. Nothing has been pushed.

**Accepted by operator (not changed)**
- Worksheets whose customer or vendor is inactive in the source are rejected whole (baseline behaviour, `ValueError … has no partner`): about 124 worksheets with a resolvable SO. Operator decision 2026‑10‑09: exclude; small and old.

**Source-data limitations (reported, not defects of the fix)**
- 561 worksheets have lines whose `SPO_ID` does not resolve to a `Source='SO'` order → no sale order, no transaction; lines counted as rejected.
- Unit prices are stored at 2 decimals; sub-cent drift against `SAmount`/`PAmount` on ~2 300 lines.
- `S` weight UoM maps to `uom.product_uom_ton` (metric tonne); 7 lines.

**Representation limitations (by design of the mapping SSOT)**
- Approved positive A/S adjustments (31 debit memos) are created as `out_invoice` with `debit_origin_id` but are not added to `revenue_total` (no native field without a further dependency).
- GL 50300/50600 handling/equipment payables are carried as the `other_expenses` float, not as bills (mapping says not COGS; no seeded accounts).
- Historical invoices and bills stay draft until the operator posts after QuickBooks reconciliation.
- Purchase orders remain RFQ (`draft`); `date_approve` is not set (pre-existing importer design).
- `legacy_erp_cp_X` and `legacy_erp_address_Y` both point at the company partner (baseline identity design); the duplicate-marker gate is on (name, model) and is 0.

**Environment**
- A fresh install loads `generic_coa` after `plasticos_accounting`, wiping its 58 account seeds; the proof DB needed a scoped `-u plasticos_accounting`. Pre-existing install-order issue, not touched.

## 13. PR

| Item | Value |
|---|---|
| Existing PR | #227 (`feat/erp-native-mapping` → `Staging`) — carries the same fixes in `3f000dc`/`6b0111f` together with unrelated UI changes |
| Isolated branch | `fix/erp-import-remediation` @ `4ef5e80` (+ this report) — **not pushed**; to be published with `make pr` once the environment is back |

---

### Evidence index (`docs/reports/evidence/erp-import-2026-10-09/`)

| File | Content |
|---|---|
| `run1_summary.json` | machine summary of the completed first run (reconciliation closes, duplicates 0) |
| `run1_log.txt` | container log of that run (source database name redacted) |
| `run1_dump_excerpt.txt` | normalised dump rows for 54839, 53797, the cutoff boundary, and the shared-order example |
| `source_counts.txt`, `source_54839_53797.txt`, `source_cutoff.txt` | source-side facts read directly from SQL Server |
| `db_pristine.txt`, `runtime_tests.txt` | target DB pristine check; Odoo runtime test result (import tests) |
| `runtime_tests_f3.txt`, `f3_rules.txt` | F3 runtime test result and the `purchase.order` rule set on a DB installed from this branch |
| `run_import.sh`, `collect.sh`, `snapshot.sql`, `dump.sql` | exact commands to reproduce run 1 / run 2 and the normalised comparison |
