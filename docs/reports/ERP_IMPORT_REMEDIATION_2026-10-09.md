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
| F7 | No real-runtime proof; replay not deterministic | `_differs` flagged `Command.clear()` vs empty, date strings, float noise as changes; Odoo 19 confirm overwrote `date_order` | `_differs` normalised; `_prepare_confirmation_values` keeps source date under `import_mode`; product-cache `exists()` guard | `test_two_worksheets_on_one_sale_order_compile_two_transactions_and_replay_adds_nothing` (in-process replay: created 0, snapshot identical) | Full first run completed (§6); **full second run not completed** (§7, §14.6) | **Partially proven — blocked on source access, see §14.6 / §14.8** |

> **2026-10-10 (session 2):** F5 is closed at document level in §14.2 (debit memos now enter `revenue_total`); the
> §12 "source-data limitations" on price precision and short tons are corrected in §14.4 (no stored drift in
> Odoo 19; short tons were mapped to the metric tonne and are now 2,000 lb); the 561 unresolved sale links are
> censused in §14.3 with the instrument that now ships in the importer. F7 remains the one open item.

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
- `scripts/install_smoke.sh` (compose mode) passed CLI arguments to `docker compose run odoo-test`, which replaces the service `command` and dropped `--addons-path`; the image's `odoo.conf` then exposed `/mnt/extra-addons` only and every Enterprise module installed as `missing`, failing `make pr-check`. Previously masked by the pr-check content cache. Fixed in this PR: the addons path is passed explicitly in both network modes; `make install-smoke` now passes with all `l10n_us*` modules installed.

## 12a. Review findings on PR #231 (Codex, 4 × P1) — all addressed

| File | Finding | Disposition |
|---|---|---|
| `plasticos_partner_import/scripts/validate_partner_layer.py:184` | `check_full_run_extension` discarded `env` and treated a missing `installed` set as empty, so every full `ERP_DRY=1` preview was refused | Fixed: the installed set is read from `env` when not supplied; `test_full_dry_run_proceeds_on_a_complete_database` |
| `…/validate_partner_layer.py:35` | Full-run preflight required only `sale`/`purchase`/`account`; a database without `plasticos_transaction` or `plasticos_accounting` passed and committed partners before reporting no transaction outcome | Fixed: `FULL_RUN_MODULES` adds both provider addons; the full run fails before any write (`tests/test_erp_layer_gate.py`, 35 pass) |
| `plasticos_transaction/models/native_document_import.py:295` | A worksheet whose sale headers resolve to different customers put every line on the first customer's invoice | Fixed: such a worksheet is rejected (`ValueError`, anomaly, no documents); the shared-order test now uses one customer and asserts a single two-line invoice to it; new `test_worksheet_whose_sale_orders_have_different_customers_is_rejected`. Source has 0 such worksheets |
| `plasticos_facility_profile/models/res_partner.py:300` | "Redefines the native stored `mobile` column without migration; breaks searches" | Partly a false premise: Odoo 19 `res.partner` has no `mobile` field (verified in `~/dev/odoo-19` base and on the fully-installed smoke DB), so nothing exists to migrate. The searchability point stands and is fixed with `search="_search_mobile"`. The probe also found `_inverse_mobile` creating the phone line without `number` (NOT NULL violation on first write) — fixed. Runtime probe: create/search/update/clear all pass (`evidence/mobile_probe.txt`) |

Runtime re-verification on a fresh DB installed from this branch: **0 failed, 0 errors of 14 tests** (`evidence/runtime_tests_review_fixes.txt`). Versions bumped: `plasticos_transaction` 19.0.2.3.25, `plasticos_partner_import` 19.0.2.10.15, `plasticos_facility_profile` 19.0.5.3.10.

Gate corrections found while publishing: (1) `scripts/pr_autopilot.py` counted every P1 bot comment as a blocking `REAL_BUG` forever, including comments whose line was already rewritten by a later push, so a PR could never pass `make pr` once reviewed — inline comments with `line: null` (GitHub's "outdated" marker) or a resolved review thread (GraphQL `isResolved`) are now skipped and counted separately (`test_outdated_or_resolved_inline_bot_comments_do_not_block`, fail-open test); the four Codex threads were answered with the fix evidence and resolved. (2) `scripts/git_open_pr.sh` read the PR head once immediately after the push and failed the publication proof on GitHub's propagation lag (twice tonight); it now re-reads up to six times, five seconds apart, for a SHA mismatch only.

## 13. PR

| Item | Value |
|---|---|
| Existing PR | #227 (`feat/erp-native-mapping` → `Staging`) — carries the same fixes in `3f000dc`/`6b0111f` together with unrelated UI changes |
| Isolated branch | `fix/erp-import-remediation` @ `4ef5e80` (+ this report) — published as **PR #231** (`b5a1389` after the review fixes); session 2 continues on the same branch (§14) |

---

## 14. Session 2 (2026-10-10) — F5 closure, source exception census, F7 status

Contract: *ERP Native Import | F5/F7 Closure and Source Exception Census*. Entry state: PR #231 open,
head `b5a1389`, base `Staging`, mergeable, no other agent's commits on the branch. Work was done in a
dedicated worktree of that branch; no other PR branch was edited.

### 14.1 Commit and environment identities

| Item | Value |
|---|---|
| Code commit (this session) | `a2f9732` — `fix(import): close F5 economics, census the source exceptions, carry short tons in pounds` |
| Report commit | the commit following it on `fix/erp-import-remediation` (this file + evidence) |
| Session host | Claude Code cloud container (Linux, no Docker daemon, no access to the operator's lab network) |
| ERP source (SQL Server) | **not reachable from this host** — `ERP_SQL_*` unset, `host.docker.internal:1433` unroutable, `pymssql` not installed in the system interpreter (`evidence/f7_environment_probe.txt`). No SQL Server read was attempted or simulated. |
| Frozen grid used for source-side census | `plasticos_partner_import/erp_extracted_data/bulk/` (2026-08-07 extract; `WKSDetail` 11 303 lines vs 11 441 read by the 2026-10-09 SQL run; no `PO` / `PODetail` / `BuySell` / `SPO_ID` / `PPO_ID`) — regression fixture, not runtime authority (ADR-021) |
| Odoo runtime for ORM tests | Odoo 19.0 Community nightly `odoo-19.0.post20261009` (nightly.odoo.com), Python 3.12 venv, PostgreSQL 16.15, database `erp_rt` created in this session with `-i plasticos_transaction,plasticos_security_base,account_debit_note --without-demo`, pristine before tests, dropped with the container. **Not** a disposable import target: no ERP source was available to import into it. |
| Modules touched | `plasticos_transaction` 19.0.2.3.25 → **19.0.2.3.26**; `plasticos_partner_import` 19.0.2.10.15 → **19.0.2.10.16** |

### 14.2 F5 closure — document-level accounting reconciliation

**A1 — customer debit adjustments.** `plasticos.transaction._compute_financials` now reads the
customer document set once each: `revenue_total = invoice + Σ debit notes (debit_origin_id = invoice,
not cancelled) − Σ credit notes (reversed_entry_id = invoice, not cancelled)`. Each imported adjustment
carries exactly one of those two links (`_customer_adjustments`), so no document is netted twice and a
credit linked to the invoice is subtracted once. `account_debit_note` (Odoo CE, already installed on the
2026-10-09 proof database) is now a declared dependency of `plasticos_transaction`, which is what makes
`debit_note_ids` a field the compute can depend on; no new field, model, or ledger was added.

Runtime proof (`test_worksheet_54839_keeps_credit_freight_costs_and_excludes_prepay`, extended with a
`GPLedger` row 5698, `Source A / AdjType S / Approved Y / Sale +150 / DM 54839`):

| Document | Odoo | Link | Effect on `revenue_total` |
|---|---|---|---|
| `legacy_erp_outinv_54839` | `out_invoice` 9 763.95 | — | +9 763.95 |
| `legacy_erp_ledger_5698` | `out_invoice` 150.00 | `debit_origin_id` → invoice; `invoice.debit_note_ids == debit` | +150.00 |
| `legacy_erp_ledger_5694` | `out_refund` 382.90 | `reversed_entry_id` → invoice; `invoice.reversal_move_ids == credit` | −382.90 |
| **transaction 54839** | | | **9 531.05** = `invoice.amount_total + debit.amount_total − credit.amount_total` (asserted) |

Source identity (`legacy_erp_ledger_<LedgerID>`), dates (`TradeDt`), partners (`AdjCpID`, falling back
to the invoice customer), memo (`AdjMemoNo` on `ref`, title on the line) and worksheet association
(`invoice_origin`) are unchanged from session 1. Worksheet 53797 still nets to revenue 0.00 and margin
−2 000.00 (`test_worksheet_53797_nets_to_zero_revenue_and_negative_margin`).

**A2 — vendor expenses (Payables by GL lookup).** Audited on the frozen grid
(`evidence/grid_census.txt`, 14 453 rows); the direct-SQL run emits the same buckets live in
`<report>-census.json` (§14.3).

| GL lookup | Rows | Worksheets | Amount | Vendors | With invoice no. | Routing (unchanged where the SSOT owns it) | Counted in economics |
|---|---|---|---|---|---|---|---|
| 50100 Purchases | 6 652 | 6 156 | 19 972 246.32 | 603 | 6 492 | vendor bill / vendor credit on `50100 Material Cost`, one per `PayableID` | once, `purchase_cost_total` |
| 50200 Inland Freight | 6 686 | 4 858 | 4 928 429.65 | 347 | 6 562 | freight bill / credit on `50200 Freight Cost`; never material | once, `freight_cost_total` |
| 50300 Handling | 475 | 314 | 319 857.55 | 37 | 458 | **not a COGS account** per the mapping SSOT (`gl_account_crosswalk.not_these_two_accounts`); no seeded account → signed total carried once as `other_expenses` | once, `cost_total` |
| 50600 Equipment | 43 | 36 | 153 681.86 | 15 | 41 | same as 50300 | once, `cost_total` |
| blank | 597 | 498 | 314 375.05 | 158 | 597 | no account in `Payables` **or** in the `WksDelivery` item the row references → **not realized** (anomaly with amount) | **not counted** — operator decision below |
| in a `PrePay=1` batch | 0 on the grid (38 batches, 0 rows; 41 `PrepayLedger` rows are not projected) | | | | | omitted, as before | — |
| 50100 with inactive vendor | 63 | | 85 078.02 | | | worksheet rejected whole (baseline rule, accepted 2026-10-09) | — |
| 50200 with inactive vendor | 10 | 10 | −2 615.63 | | | unbillable; see freight-once below | — |

Findings and what changed:

- **Handling and equipment rows are real vendor invoices** (458 of 475 and 41 of 43 carry invoice numbers, all carry a vendor, a batch and `Posted=1`; top vendors TLC Worldwide Logistics, JEI Inc, Greenview Materials; Butler Paper Recycling, Bonnette Auction). The SSOT excludes both accounts from the COGS crosswalk and nothing seeds a handling or equipment expense account, so the importer cannot lawfully realize them as bills without inventing an account mapping. They stay a single `other_expenses` amount per worksheet (counted once in `cost_total`), and the importer now **records every one of them** with vendor, invoice number and amount as an anomaly and tallies them in the census (`gl_50300_as_other_expenses`, `gl_50600_as_other_expenses`) instead of folding them silently. **Operator decision required:** seed `50300 Handling` / `50600 Equipment` (or name existing accounts) if these 518 rows / 473 539.41 should become native bills; this PR does not extend the chart.
- **597 blank-GL payables (314 375.05, 498 worksheets, mostly 2023–2026, vendors such as Stericycle, 48 Forty Solutions, S&B Pallet) were being dropped with a one-line anomaly and no dollar.** The `WksDelivery` item each one references also carries a blank GL, so no projection resolves an account for them. They are now reported with their amount per row and tallied (`gl_blank_not_realized`). **Operator decision required:** the GL these rows belong to (the vendors suggest disposal, pallets and packaging — not material, not freight).
- **Freight is counted once.** Before: a freight row that could not be billed (inactive vendor; 10 rows, all credits, on worksheets that also have billable freight) was added to `freight_actual`, which `_compute_financials` ignores whenever freight bills exist — a silent undercount shown as a misleading `freight_actual` on the record. Now: on a worksheet that has freight bills the unbilled amount is not written anywhere, is reported as `unbilled freight X not counted: worksheet has freight bills`, and is tallied (`gl_50200_unbilled`). A worksheet with **no** freight bill keeps the `freight_actual` fallback as before. Runtime test `test_unbilled_freight_row_is_not_folded_beside_freight_bills` (`freight_cost_total` 600.00, `freight_actual` 0.00, anomaly present).
- Material bills keep their one-row-per-`PayableID` identity, vendor, amount, date, reference and worksheet; 54839 still carries 9 366.52 / −9 366.52 / 8 826.48 on `50100`, net 8 826.48. `PrePay=1` rows stay excluded with their amount tallied (`prepay_batch_omitted`); `PrepayLedger` is still not projected. No settlement is inferred (payments 0, entries 0 — F2 tests unchanged).

### 14.3 The 561 unresolved sale links — census

**What the 561 is.** The 2026-10-09 SQL run rejected 2 432 rows; its summary `errors` list (capped at
1 000 by the shared contract) holds only partner-layer rows, so the 561 figure in §12 came from the
console, not from an artefact. Reading the importer: a line whose `SPO_ID` resolves no `Source='SO'`
header but whose `PPO_ID` resolves a purchase header was **not** rejected — it was placed in the purchase
group, its purchase order and vendor bills were written, no sale order / invoice / transaction was
compiled, and the worksheet was still counted as a *created transaction*. The 561 are therefore
**worksheets** (not lines) that produced purchase-side documents with no transaction, and their exact
root causes were never written down. That is an importer accounting defect, fixed as follows.

**Instrument shipped (this is the census; it needs the SQL source to produce the final numbers).**

- `header_for_line` now names a cross-linked number: `SO 8022 matched 0 headers (exists as PO)` is a
  different source condition from a number no header carries.
- `_realize_one` records every side that resolves no header, with its own reason, even when the other
  side links (`WKSDetail <id>: sale link: <reason>` / `purchase link: <reason>`), and marks a worksheet
  with purchase links and no sale link: `no sale order link: purchase documents realized, no transaction
  compiled`. Nothing manufactures a sale order; the purchase order and bills are kept on their own
  identity, exactly as the established join `WKSDetail.SPO_ID/PPO_ID → PODetail.PO_ID → PO` allows.
- `native_orders.link_census` groups the failures by **side × root cause** —
  `blank_key`, `key_without_order_line`, `order_line_without_number`, `number_under_other_source`,
  `number_without_header`, `number_with_several_headers` — with lines, distinct worksheets, distinct
  keys, and the sale / purchase dollars on those lines; and gives the **worksheet view** the line view
  cannot: worksheets with no sale link at all, how many still link on the purchase side, whether the
  source holds a base-trade sale ledger row, customer receipts or payables for them, whether the
  counterparty is active, their order years and worksheet status, and the exact worksheet numbers.
- The census is written beside the summary as `<ERP_REPORT_PATH minus .json>-census.json`
  (`census`, every `anomaly`, every `unresolved` row — the shared summary schema allows no extra keys),
  and printed after the summary. Payables routing (§14.2) and price precision (§14.4) are in the same
  file.

Covered by `tests/test_erp_native_orders.py` (pure python: reason classes, census counts, partner and
document flags, cross-source reason) and by the runtime test
`test_worksheet_without_a_sale_link_keeps_its_purchase_documents_and_is_censused` (two worksheets, one
blank key and one cross-linked number: no SO, no invoice, no transaction, both POs and the bill written,
`transactions.rejected` 0, both anomalies present, census worksheets 2 / with purchase link 2 / ledger
1 / receipts 1 / payables 1 / partner active 2 / 1 550.00 sale, 1 040.00 purchase, years {2020: 2}; a
replay creates nothing and the census is stable).

**Source-side proxy on the frozen grid** (`evidence/grid_census.txt`; header references `SPo` / `PPo`,
which are the order numbers, not the `SPO_ID` / `PPO_ID` foreign keys the live join uses — so this is
the shape, not the final count):

| Proxy | Lines | Worksheets | Sale $ | Purchase $ | Notes |
|---|---|---|---|---|---|
| lines with blank `SPo` | 1 189 | 737 | 1 036 095.72 | 942 992.35 | 695 of the lines still name a `PPo` |
| worksheets with no `SPo` on any line | 681 | **485** | 930 671.19 | 926 699.04 | 411 have a purchase reference, 328 have a base-trade sale ledger row (the source invoiced a customer), 12 have receipts, 367 have payables; trade years 2023: 49, 2024: 119, 2025: 125, 2026: 25, unknown 113 |
| lines with blank `PPo` | 903 | 535 | 1 588 629.76 | 1 061 139.37 | 409 still name an `SPo` |
| worksheets with no `PPo` on any line | 559 | 350 | 1 543 364.42 | 1 056 100.69 | 276 have a sale reference; these do compile a transaction (sale side present) without a native PO |

Dollar exposure of the sale-side gap is therefore of the order of **0.9–1.0 M of historical sales on
~485–561 worksheets, most of them 2024–2026 and most of them with a customer invoice in the source** —
not immaterial, and not something a join change can fix: a blank or dangling `SPO_ID` is source data.
**Operator decision required:** whether a worksheet with a valid customer trade (ledger `Source B`
sale, receipts) but no sales-order link should have its customer invoice realized from the worksheet
lines and `BuySell.CustID` alone. That would create an invoice without a sale order and a transaction
without `sale_order_id` (the compiler hangs off `sale.order.action_confirm`), which is a design
change outside this contract; it is not done here.

**Not conflated:** 561 ≠ 561 lines (the grid proxy shows ~1.4 lines per such worksheet); the final
FK-level counts per root cause come from `<report>-census.json` of the next direct-SQL run (§14.6).

### 14.4 Short-ton and price-precision reconciliation

**Short tons.** `_UOM_XMLID` mapped source UoM `S` to `uom.product_uom_ton`, which Odoo seeds as the
**metric tonne** (`relative_factor` 1000 on `product_uom_kgm`, `addons/uom/data/uom_data.xml`). The 7
source lines using `S` (DetailIDs 1715, 3148, 5914, 6471, 10945, 11380, 13653 — listed in
`evidence/grid_census.txt`) would have been 10.2 % heavier than the worksheet says. Fix:
`native_orders.native_quantity` carries `S` as pounds at **2 000 lb per short ton** (the factor
`plasticos.transaction.line` already uses), on sale lines, purchase lines, invoice lines and worksheet-
priced bill lines; `SWeight` / `PWeight` stay the only quantity source; `PODetail` placeholders stay
excluded; the per-pound rate is `amount ÷ (weight × 2 000)` so the line amount is unchanged. Odoo CE
seeds no short-ton unit and none was added. Runtime test
`test_short_ton_lines_are_carried_in_pounds_at_two_thousand_per_ton` (20 S → 40 000 lb on the SO line,
PO line, invoice line and bill line, all in `uom.product_uom_lb`, 1 950.00 / 1 840.00 preserved).

**Price precision — the §12 claim was wrong.** Odoo 19 declares `price_unit` on `sale.order.line`
(`addons/sale/models/sale_order_line.py:177`), `purchase.order.line`
(`addons/purchase/models/purchase_order_line.py:46`) and `account.move.line`
(`addons/account/models/account_move_line.py:399`) with `min_display_digits='Product Price'` and **no
`digits`**: the column is `float8`, `Float.get_digits` returns `False`, and the stored value is the
full `amount ÷ weight`. `Product Price` (2) governs display only. Quantities store at `Product Unit`
(2 decimals); the source weights have 0 decimals on 22 601 line-sides and 2 on 5, so they store exactly
too.

| Comparison (grid, sale + purchase line-sides with an amount and a weight) | Lines | Net drift | Abs drift | Max |
|---|---|---|---|---|
| **as stored** (unrounded price × quantity at 2 dp) | **0** | 0.00 | 0.00 | 0.00 |
| if the price were rounded to 2 dp (display) | 2 282 | 195 266.17 | 238 376.07 | 239.10 |
| … 3 dp | 886 | 1 501.77 | 4 476.45 | 79.29 |
| … 4 dp | 760 | 87.00 | 369.10 | 79.29 |
| … 6 dp | 193 | −0.20 | 2.52 | 0.42 |

So the "~2 300 sub-cent discrepancies" are the lines whose per-pound rate has more than two decimals
(e.g. 0.2441/lb); their invoices, bills, SO and PO lines carry the source amount to the cent. Runtime
proof: `test_sub_cent_unit_price_keeps_the_source_amount_and_is_only_rounded_for_display` — 10 000 lb
sold for 2 441.00 → `price_unit` 0.2441 on the SO line and the invoice line (re-read from the database
after `invalidate_all`), `price_subtotal` 2 441.00, `amount_total` 2 441.00, `revenue_total`
2 441.00. The importer now measures drift against the fields' **storage** precision
(`_stored_digits`, read from the field definitions, not from `decimal.precision`) and reports any line
whose stored quantity × price would not reproduce the source amount (`price_precision` in the census:
`digits` null, `quantity_digits` 2, `display_digits` 2, lines 0) — covered by
`test_source_amount_drift_is_reported_when_a_quantity_cannot_be_stored_exactly` (3.333 lb → 3.33, two
anomalies with the stored amount, tally 2 lines) and `tests/test_erp_native_orders.py::test_amount_drift_…`.
No decimal-precision setting was changed; none needs to be.

### 14.5 First run — counts

No full direct-SQL run could be executed in this session (§14.1, §14.6). The last completed first run
remains the 2026-10-09 one in §6 (`records_seen 32 332 = 25 694 + 2 115 + 2 091 + 2 432`,
`duplicates 0`, `final_status partial`), executed on code **before** the product-cache fix and before
this session's changes. Its counts are therefore evidence of the pipeline, not of this HEAD.

### 14.6 Second run — status

**Not executed.** Pre-execution safety checks from the contract, applied honestly:

| Check | Result |
|---|---|
| 1. Exact source SQL Server database and immutable snapshot | **Cannot be identified from this host.** The restored ERP database lives on the operator's lab (`host.docker.internal:1433` from the `odoo19` compose project); this cloud container has no Docker daemon and no route to it (`evidence/f7_environment_probe.txt`). |
| 2. Target database, environment, compose project, addons revision | Local `erp_rt` on PostgreSQL 16.15 with this worktree's addons exists (used for ORM tests), but without check 1 it is not an import target. |
| 3. Target disposable, no production data | `erp_rt` is fresh and empty of business data (true). |
| 4. No other agent on the DB / containers | True for `erp_rt`; unknowable for the operator's `odoo19` project. |
| 5. Refuse if any identity check is ambiguous | **Refused.** No partial or simulated run is reported as F7 evidence. |

What is ready for the operator to run (unchanged ceremony, `evidence/run_import.sh run1` then
`run2` with `ERP_REQUIRE_EMPTY=0`, `collect.sh`, `diff run1_dump.txt run2_dump.txt`), now additionally
producing `erp-import-run{1,2}-census.json`; the acceptance for run 2 stays: created 0 in every bucket,
identical normalised dump, duplicates 0, census identical to run 1. In-process replay coverage on this
HEAD: `…replay_adds_nothing` (shared SO) and `…without_a_sale_link…` (PO-only worksheets) both assert an
identical snapshot and `created 0` on the second `realize()`.

### 14.7 Test results

| Tier | Scope | Result |
|---|---|---|
| Pure python (`pytest tests/`, system Python 3.13, no Odoo) | whole repo | **1 100 passed, 48 skipped** (session 1: 1 093 passed) |
| Pure python, branch subset | `tests/test_erp_native_orders.py` (28, +7 new), `test_phantom_enum_values.py`, `test_repo_dependency_integrity.py` | **73 passed** |
| **Odoo 19 runtime** (`odoo -u plasticos_transaction --test-enable --test-tags /plasticos_transaction,/plasticos_security_base`, database `erp_rt`, local nightly runtime, §14.1) | `plasticos_transaction` 17 tests (11 from session 1 + debit-memo assertions + 5 new: unbilled freight, short tons, display-only precision, quantity-precision drift, no-sale-link census) and `plasticos_security_base` 4 access tests | **0 failed, 0 errors of 19 tests** (`evidence/runtime_tests_f5_census.txt`; Odoo counts 17 + 6 class-level entries as 19 results) |
| Static gates (worktree) | `ruff check` / `ruff format --check` (0.16.0), `check_module_wiring.py` (30 modules), `check_circular_deps.py`, `check_odoo19_xml.py`, `check_orphan_model_refs.py` | all pass |
| Not run here | `make install-smoke` (Docker), `make pr-check` remote lanes, `ci/odoo.sh` | run by `make pr` / CI on publication |

Two runtime-only facts were caught by the runtime tier and would have been invisible to pure-python
tests: (1) the earlier belief that `price_unit` is stored at two decimals (it is not — the first runtime
run of the drift test produced an invoice of 2 441.00 where the pure-python model predicted 2 400.00),
and (2) `Float.get_digits` returning `False` rather than `None` for such a field.

### 14.8 Accepted exceptions vs blockers

**Blockers (genuine)**

- **F7 full first run + replay on this HEAD** — needs the restored SQL Server snapshot, which only the
  operator's lab reaches. Everything needed to run it is on the branch; nothing else is outstanding.
- **Final FK-level 561 census numbers** — produced by that run (`-census.json`); the grid proxy in
  §14.3 bounds them (485 worksheets / 0.93 M sale on the older grid).

**Operator decisions (reported, not decided here)**

- 597 blank-GL payables, 314 375.05, 498 worksheets — which account, or confirm exclusion.
- 518 handling / equipment payables, 473 539.41 — native bills on seeded `50300` / `50600` accounts, or
  keep as `other_expenses`.
- Worksheets with a customer trade but no sale-order link (≈485–561, ≈0.9–1.0 M sales) — realize the
  invoice from the worksheet without a sale order (design change), or accept as purchase-only history.

**Accepted (unchanged)**

- Inactive-counterparty worksheets rejected whole (2026-10-09 decision); 10 unbillable freight credits
  (−2 615.63) now reported per worksheet rather than hidden.
- Historical documents stay draft; purchase orders stay RFQ; QuickBooks owns settlement.

**Closed by this session**

- F5: debit memos in revenue; vendor expense routing audited and every non-billed row reported with its
  amount; freight counted once.
- Short tons at 2 000 lb; price precision shown to be display-only with zero stored drift.
- Transaction accounting for PO-only worksheets is no longer silent; the census instrument ships.
- Publication hygiene: the mapping runbook directory introduced in session 1 (`docs/runbooks/erp sync mapping
  matrix/`) is renamed to `docs/runbooks/erp_sync_mapping_matrix/`; the governance `make pr` writer stage splits
  changed paths on whitespace and refused the branch on that path alone. The repo's own `make pr` refuses on
  `gh auth status`, which reports a sentinel token on this surface while the REST transport works; publication
  therefore went through the governance `make pr` (`PR_BASE=origin/Staging`, `PR_REMEDIATE=0`).

---

## 15. Session 3 (2026-10-10) — import accounting and unresolved-bill convergence (GMP-001)

Contract: *PR #231 Final Code Convergence*, audited HEAD `866d6f1`. GMP run `GMP-001`
(`reports/GMP-Report-001-erp-import-accounting-convergence.md`, a local artifact the repository keeps out of git by convention). Code commit `7195393`. F1–F6 repairs
untouched; no ADR, mapping SSOT, chart seed, security file or other branch was modified; BAN001 honoured.

### 15.1 Import outcome accounting

A worksheet whose lines link on the purchase side only used to be counted as a **created**
`transactions` row (or **skipped** on replay) although no `plasticos.transaction` exists for it. It is now
counted as **rejected** in the `transactions` bucket: its purchase order(s) and vendor bills are still
realized on their own identity, the missing sale link is reported per line with its root cause, the
worksheet is named in the census (`worksheets.without_sale_link`), and a replay reports the same outcome.
The summary contract wording (`erp/summary.py`) now defines a rejected `transactions` row this way, so
`records_seen = created + updated + unchanged + rejected` still closes and nothing is double-counted.
Runtime proof: `test_worksheet_without_a_sale_link_keeps_its_purchase_documents_and_is_censused` —
two PO-only worksheets → `transactions` created 0 / skipped 0 / rejected 2, `transaction_lines` created 2
(the purchase-side lines), both POs and the bill written, replay rejected 2 / created 0, snapshot identical.

### 15.2 Native-account crosswalk audit and quarantine of unresolved bills

The mapping SSOT's `gl_account_crosswalk` names exactly two accounts (`50100` → Material Cost,
`50200` → Freight Cost) and lists `50300` / `50600` under `not_these_two_accounts`; no other entry
exists, and `plasticos_accounting` seeds no handling, equipment, or catch-all payables account. There is
therefore **no authoritative mapping** for handling, equipment, or blank-GL rows, and none was invented.
Every payable row the import does not write is now **quarantined** with its full source identity —
`payable_id`, `worksheet`, `vendor` (`CpID`), `invoice_no`, `invoice_date`, `amount`, `gl`, `batch`,
precise `reason`, `disposition` — in `census.unresolved_bills` of `<report>-census.json` and as a
per-row anomaly carrying the same fields.

| Disposition | Rows / amount on the frozen grid | Native document | In transaction economics | Meaning |
|---|---|---|---|---|
| billed (`50100`, `50200`) | 13 338 / 24 900 675.97 | vendor bill or credit, one per `PayableID` | yes, once | **fully imported** |
| `transaction_only_cost` (`50300`, `50600`) | 518 / 473 539.41 | none | yes, once, as `other_expenses` | cost carried, **bill not realized** |
| `not_realized` (blank or unknown GL) | 597 / 314 375.05 | none | **no** | **unresolved source bill** |
| `unbillable` (owner exists; vendor not imported, no journal, zero amount) | 10 freight credits / −2 615.63 | none | no (reported per worksheet) | unresolved source bill |
| `prepay_omitted` (`PrePay=1` batch) | 0 on the grid (38 batches hold no Payables row) | none | no | excluded by rule |

### 15.3 Reconciliation

`census.payables_reconciliation` closes the loop per run: `rows_seen` (payable rows of worksheets that
were not rolled back) `== billed_rows + quarantined_rows`, with amounts and a `by_disposition` tally;
when it does not close the run records a `Payables / reconciliation` anomaly. A quarantined row is by
construction never a native bill (the quarantine is written on the branches that `continue` before
`_move`), so an unrealized bill cannot be read as imported. Runtime proof on worksheet 54839 (now with a
blank-GL row 600009, 40.00): 8 rows seen = 5 billed (9 426.48) + 3 quarantined (5 140.00:
transaction_only_cost 100.00, not_realized 40.00, prepay_omitted 5 000.00); `cost_total` 9 526.48 carries
the handling cost once and the blank-GL amount not at all; `closes` true.

### 15.4 F5 status, stated precisely

F5 is **closed for every bill that has an authoritative account** (material and freight: identity,
vendor, amount, date, reference, worksheet preserved; credits and debit memos in revenue once). It is
**not complete**: 518 handling / equipment bills (473 539.41) are carried as transaction-only cost without
a native document, and 597 blank-GL bills (314 375.05) plus 10 unbillable freight credits (−2 615.63) are
neither documents nor costs. Those 1 125 rows / 785 298.83 are quarantined with full identity and await
the operator's account decision (§14.8); the import does not claim them.

### 15.5 Tests and gates

| Tier | Result |
|---|---|
| Pure python, `tests/test_erp_native_orders.py` (+2: quarantine identity, reconciliation) and the ERP subset | 100 passed |
| Pure python, whole repo | 1102 passed, 48 skipped |
| Odoo 19 runtime, `/plasticos_transaction,/plasticos_security_base` on `erp_rt` | **0 failed, 0 errors of 19 tests** (`evidence/runtime_tests_gmp001.txt`) |
| ruff 0.16.0 check/format, py_compile, module wiring, circular deps | pass |

### 15.6 Deferred (unchanged)

The full direct-SQL first run and replay, and the FK-level 561 census, stay deferred until the
operator's restored source database is reachable (§14.6). No alternate access was attempted and no proof
was manufactured.

---

## 16. Session 4 (2026-10-10) — payable coverage and economic dispositions (GMP-002)

Contract: *PR #231 Final Accounting-Integrity Remediation*, audited HEAD `085f9d6`. Code commit `889ea80`.
No ADR, mapping SSOT, chart seed, security file, business rule, or other PR was touched; BAN001 passes on all
tracked content (`ci/check_banned_identifier.py`: OK).

### 16.1 Defect 1 — payable coverage

Three paths let applicable source payables disappear from both sides of the reconciliation, which then
closed as if they did not exist:

| Path | Before | Now |
|---|---|---|
| Worksheet with lines but no valid sale **or** purchase link (`_realize_one` early return) | returned before `_vendor_bills`; its payables neither billed nor quarantined | every payable quarantined (`not_realized`, "worksheet has no valid sale or purchase order link; no document to attach the bill to"), tallied as `no_order_link_not_realized`, counted in `rows_seen` |
| Worksheet rolled back by an exception | its attempt's rows dropped from both sides | the attempt's rows purged, every payable re-quarantined (`not_realized`, "worksheet rolled back (…); no document of it exists"), tallied as `worksheet_rolled_back_not_realized` |
| Payable whose `BuySellNo` is not a worksheet with lines, or blank | never visited by `realize()`; blank references dropped at index time | `SourceIndex` keeps blank-reference payables under key `""`; after the worksheet loop every such row is quarantined (`not_realized`, "BuySellNo '…' is not a worksheet with lines; no transaction to attach the bill to" / "blank BuySellNo; the bill names no worksheet"), tallied as `outside_worksheet_universe_not_realized`, counted in `rows_seen` |
| Worksheet left out by a diagnostic `ERP_LIMIT` | silent | counted in `census.payables_unselected` (rows, amount); not part of the reconciliation, never claimed |

**Why the outside-universe rows exist (source contract).** `SourceIndex.buysell_numbers()` defines the
transaction universe as every `BuySellNo` that owns a `WKSDetail` line; a payable can attach to a native
document only through that worksheet. On the frozen grid 610 `Payables` rows (291 523.44) carry a
`BuySellNo` that is no such worksheet: 510 distinct free-text references (`51694 / 4714`, `51715R`,
`51685-1`, …), of which 597 rows have no GL lookup, 7 are GL 50100 and 6 are GL 50200. The contract excludes
them from transactions legitimately (nothing to attach to), but not from *reporting*: they are now listed
one by one. The 13 rows with a native account are flagged in their reason as an **operator decision**
(realize standalone, unattached bills, or confirm exclusion); the importer does not invent a transaction for
them. Blank `BuySellNo`: 0 rows on the grid.

**The §15.2 blank-GL figure, corrected.** The 597 blank-GL rows counted in §15.2 are the same rows: they
are outside the worksheet universe, so a real run would never have reached the `gl_blank_not_realized`
branch for them. They now surface under `outside_worksheet_universe_not_realized` instead, with the same
dollar exposure.

### 16.2 Defect 2 — economic dispositions

| Case | Before | Now |
|---|---|---|
| GL 50300 / 50600 on a worksheet with no transaction (purchase-only) | `transaction_only_cost`, amount added to `costs["other"]` that nothing ever carried | `not_realized`, "GL … has no native account in the crosswalk and no transaction exists to carry it"; nothing added; bucket `gl_<gl>_not_realized` |
| GL 50300 / 50600 with a transaction | `transaction_only_cost` | unchanged: carried once as `other_expenses` |
| Unbillable freight on a worksheet **with** freight bills | `unbillable` | `unbillable`, "…; not counted: worksheet has freight bills" (bills are the freight cost; the row is not folded into `freight_actual`) |
| Unbillable freight, no freight bill, transaction exists | `unbillable` while `freight_actual` silently carried it | `transaction_only_cost`, "…; amount carried once as the transaction's actual freight cost" — the disposition now agrees with `freight_cost_total` |
| Unbillable freight, no transaction | `unbillable` with the amount left in `costs["freight"]` | `not_realized`, "…; no transaction exists to carry it" |
| Unbillable material (50100) | `unbillable` | `unbillable`, "…; not counted" |

GL mappings (`50100` → Material Cost, `50200` → Freight Cost) and cost ownership are unchanged; no account,
mapping, or transaction was invented.

### 16.3 Regression proof (Odoo 19 runtime, `plasticos_transaction/tests/test_erp_worksheet_import.py`)

| Test | Proves |
|---|---|
| `test_no_link_worksheet_quarantines_every_source_payable` | no-link worksheet with four payables: rejected 1, no document, 4 quarantined `not_realized`, `rows_seen` 4 = billed 0 + quarantined 4, replay identical |
| `test_purchase_only_worksheet_carries_no_handling_or_equipment_cost` | PO-only worksheet with GL 50300 and 50600: material bill written, both rows `not_realized`, no `other_expenses` bucket, reconciliation closes, replay stable |
| `test_unbillable_only_freight_is_carried_as_actual_freight_cost_when_a_transaction_exists` | unbillable-only GL 50200: `freight_actual` 55.00 = `freight_cost_total`, disposition `transaction_only_cost`; the same row on a transaction-less worksheet is `not_realized` |
| `test_payables_outside_the_worksheet_universe_and_rolled_back_worksheets_are_quarantined` | rolled-back worksheet's bill and two outside-universe rows (free-text and blank reference) quarantined with reasons; `rows_seen` 11 = billed 5 + quarantined 6; replay identical, `unresolved_bills` identical |
| `test_diagnostic_limit_counts_the_payables_it_leaves_out` | `ERP_LIMIT=1`: `payables_unselected` 8 rows / 14 566.48 (9 366.52 − 9 366.52 + 8 826.48 + 625 − 25 + 100 + 5 000 + 40; corrected in §17.3 from the 15 006.48 first written here), reconciliation closes on the selected worksheet |
| `test_unbilled_freight_row_is_not_folded_beside_freight_bills` (extended) | disposition `unbillable` with the "worksheet has freight bills" reason |

Pure-python (`tests/test_erp_native_orders.py`): `outside_universe_payables`, `payables_reconciliation`
including rolled-back and outside-universe rows, `SourceIndex` keeping blank-reference payables.
F1–F6 tests unchanged and green.

### 16.4 Test results and gates

| Tier | Result |
|---|---|
| Pure python, ERP subset | 102 passed |
| Pure python, whole repo | 1 104 passed, 48 skipped |
| Odoo 19 runtime, `/plasticos_transaction,/plasticos_security_base` on `erp_rt` | **0 failed, 0 errors of 24 tests** (`evidence/runtime_tests_gmp002.txt`) |
| ruff 0.16.0, py_compile, module wiring, circular deps, BAN001 | pass |

### 16.5 Outstanding exception totals (frozen grid; the live figures come from `<report>-census.json`)

| Disposition / bucket | Rows | Amount |
|---|---|---|
| fully imported (`50100`, `50200` on a worksheet with lines; includes the 73 inactive-vendor rows below until the run excludes them) | 13 325 | 24 923 527.58 |
| `transaction_only_cost` (50300 / 50600 on worksheets that compile a transaction; plus unbillable freight carried by `freight_actual`) | ≤ 518 (+10) | ≤ 473 539.41 (−2 615.63) — exact split by transaction existence comes from the run |
| `not_realized`, outside the worksheet universe | 610 | 291 523.44 (597 blank GL, 7 × 50100, 6 × 50200) |
| `not_realized`, no-link worksheets (grid proxy) | 35 | 41 092.24 |
| `not_realized`, rolled-back worksheets (inactive counterparty, 2026-10-09 decision) | 63 material rows | 85 078.02 |

Deferred, unchanged: full SQL-backed first import, FK-level 561 census, full replay.

## 17. Session 5 (2026-10-10) — payable identity coverage, transaction verdict, evidence consistency (GMP-003)

Contract: *GAR | PR #231 · GMP-003*, audited HEAD `0ba9115b5df7aa621f7a84ef25b5c9833fdbfcdb`. Code commit
`65cd2d3`. No ADR, mapping SSOT, chart seed, security file, business rule, or other PR was touched; BAN001
passes on all tracked content (`ci/check_banned_identifier.py`: OK). Module versions `plasticos_transaction`
19.0.2.3.29, `plasticos_partner_import` 19.0.2.10.19.

### 17.1 F1 — payable coverage

| Finding at `0ba9115` | Now |
|---|---|
| `realize()` returned at its first branch when `index.orders` was empty: every worksheet skipped, no payable quarantined, no census, no reconciliation | the branch is gone. With no order header the run still loads its context, skips every worksheet, quarantines each of its payables (`not_realized`, "source carries no order headers; no document to attach the bill to", bucket `no_order_link_not_realized`), then runs the outside-universe pass, the census and the reconciliation exactly as any other load |
| `payables_reconciliation` derived `rows_seen` from the routed rows, so a payable omitted from **both** tallies kept the equation balanced and the run closed | the source is reconciled by identity: `source_rows` is every indexed `Payables` row, and each `PayableID` must appear exactly once across billed (`context["billed_payables"]`, recorded when the bill is written or found), quarantined (`unresolved_bills`) and excluded (named below). The result lists `missing_rows`, `duplicated_rows`, `unknown_rows` (an identity the source never carried) and `blank_identity_rows` (a source row without a `PayableID` cannot be proven covered) and `closes` only when all are empty and `source_rows == billed + quarantined + excluded`. `reconciliation_gap()` renders the gap into the run anomaly (`Payables / reconciliation`) and the operator printout |
| Worksheets a diagnostic `ERP_LIMIT` left out were counted (`payables_unselected`) but sat outside the reconciliation; a dry run left every payable unaccounted | both are explicit exclusions: `payables_excluded = {rows, amount, by_reason: {diagnostic_limit \| dry_run}}`, each row recorded by identity so the identity reconciliation covers it. `payables_unselected` keeps its contract (the `diagnostic_limit` slice) |

On the frozen grid every one of the 14 453 `Payables` rows has a distinct, non-blank `PayableID`
(`grid_census.py` input; verified this session: 0 blank, 0 duplicate), so identity coverage is exact there.

### 17.2 F2 — economic truth

| Finding at `0ba9115` | Now |
|---|---|
| `has_transaction = bool(documents["sales"])`: a linked sale order was treated as an existing transaction, so GL 50300/50600 rows were `transaction_only_cost` ("carried once as other expenses") and unbilled freight was `transaction_only_cost` ("carried … as the transaction's actual freight cost") before anything was confirmed or compiled | `_vendor_bills` only decides *whether a transaction may compile*; rows whose disposition depends on it are held in `context["pending_costs"]`. `_confirm_sales` confirms the batch, compiles, then `_settle_transactions` looks the transaction up (`plasticos.transaction` named by the worksheet **and** owned by one of the worksheet's own sale orders) and dispositions each held row: `transaction_only_cost` when it exists, `not_realized` with the failure appended ("… no transaction exists to carry it (sale order S00042 not confirmed (draft))" / "… (sale order confirmed but no transaction was compiled)") when it does not. The tally buckets (`gl_<gl>_as_other_expenses` vs `gl_<gl>_not_realized`) are written at the same point |
| `report.bump("transactions", "created" if fresh_document else "skipped")` fired inside `_realize_one`, before confirmation: a blocked confirmation or failed compile still read as a created transaction | the verdict is pending until settlement: `created` when the transaction came to exist in this run, `skipped` when it already existed (replay), `rejected` with a `BuySell` anomaly naming the cause when none exists. `fresh_document` is gone; document freshness never stood for a transaction |
| | GL mappings (50100 → Material Cost, 50200 → Freight Cost), `costs["other"]` / `costs["freight"]` as compile inputs, prepay exclusion and the unbilled-freight-beside-bills rule are unchanged. No account, mapping, field or transaction was invented |

Rows and documents that are not transaction-dependent are untouched: the material and freight bills of a
worksheet whose order fails to confirm are still written on their own identity (they are documents, not
transactions) and are billed in the reconciliation.

### 17.3 F3 — evidence consistency

§16.3 reported `payables_unselected` as 8 rows / **15 006.48** for `test_diagnostic_limit_counts_the_payables_it_leaves_out`.
The fixture (`_worksheet_54839`) carries 9 366.52 − 9 366.52 + 8 826.48 + 625 − 25 + 100 + 5 000 + 40 =
**14 566.48**, which is what the test asserted and the runtime proved at `0ba9115` (`runtime_tests_gmp002.txt`,
0 failed). The 15 006.48 was a transcription error in the report (the pre-correction value of the test's
first draft), not a code or test result; the §16.3 row is corrected in place with the derivation, and no
business logic was changed to fit either number. The test now also asserts `payables_excluded` and the
identity reconciliation (`source_rows` 9 = 1 billed + 0 quarantined + 8 excluded).

### 17.4 Regression proof (Odoo 19 runtime, `plasticos_transaction/tests/test_erp_worksheet_import.py`)

| Test | Proves |
|---|---|
| `test_empty_order_graph_quarantines_every_payable_and_still_reconciles` | F1 positive: no order header, one worksheet with four payables plus one outside-universe row → skipped 1, nothing written, 5 quarantined `not_realized`, `source_rows` 5 = 0 + 5 + 0, closes, no reconciliation anomaly; replay identical |
| `test_reconciliation_does_not_close_when_a_source_payable_is_on_neither_side` | F1 negative: a census rebuilt from a context that routed two bills and nothing else keeps the routed count balanced yet reports `unaccounted_rows` 6, `missing_rows` = the six omitted `PayableID`s, `closes` False; the same identity billed and quarantined → `duplicated_rows`; end to end, a source row with a blank `PayableID` leaves `blank_identity_rows` 1 and the run anomaly "1 source rows without a PayableID" |
| `test_dry_run_excludes_every_payable_by_name_and_writes_nothing` | dry run: nothing written, `payables_excluded.by_reason.dry_run` 8 rows / 14 566.48, outside-universe row still quarantined, `source_rows` 9 = 0 + 1 + 8, closes |
| `test_blocked_sale_confirmation_is_a_rejected_transaction_that_carries_no_cost` | F2: `action_confirm` raising → order stays draft, no transaction, counts `rejected` 1 / `created` 0, anomaly "sale order S… not confirmed (draft); no transaction compiled"; material bill still written; GL 50300 and unbilled freight `not_realized` with the failure appended, bucket `gl_50300_not_realized`, no `_as_other_expenses`, closes. Second run (unblocked): `created` 1, `other_expenses` 80, `freight_actual` 55, both rows `transaction_only_cost`. Third run: `skipped` 1, snapshot identical, reconciliation and `unresolved_bills` identical to the second |
| `test_failed_transaction_compile_is_a_rejected_transaction_until_it_compiles` | F2: a second worksheet on an already confirmed order, with the standalone compile raising → order still `sale`, no transaction, `rejected` 1, anomaly "sale order confirmed but no transaction was compiled; no transaction compiled", GL 50600 `not_realized` "(sale order confirmed but no transaction was compiled)", closes. Next run: `created` 1, `other_expenses` 90, row `transaction_only_cost` |
| `test_diagnostic_limit_counts_the_payables_it_leaves_out` (extended) | F3: 8 rows / 14 566.48 under `payables_unselected` and `payables_excluded.by_reason.diagnostic_limit`; identity reconciliation closes with the eight excluded by name |

Pure-python (`tests/test_erp_native_orders.py`): `payables_reconciliation` closing on full identity coverage
with an exclusion; detecting a row on neither side (gap text "9 source rows != 3 billed + 4 quarantined + 1
excluded; 1 missing PayableID: 500868"); detecting duplicates, unknown identities, blank identities and an
excluded-and-quarantined row; `source_payable_identities` walking every indexed row. The exact-shape assertion
on the empty reconciliation was extended to the new keys. F1–F6 tests and the GMP-001/002 tests are
unchanged and green.

Why the failed-compile test uses an already confirmed order: in `import_mode`, `sale.order.action_confirm`
compiles inside the same savepoint, so a compile failure on a fresh order rolls the confirmation back and
surfaces as "not confirmed (draft)" (the blocked-confirmation test). The standalone compile that
`_confirm_sales` runs for orders confirmed earlier is the only path where a confirmed order can lack its
transaction, and that is the path the test blocks.

### 17.5 Test results and gates

| Tier | Result |
|---|---|
| Pure python, whole repo | 1 108 passed, 48 skipped |
| Odoo 19 runtime, `/plasticos_transaction,/plasticos_security_base` on `erp_rt` | **0 failed, 0 errors of 29 tests** (`evidence/runtime_tests_gmp003.txt`; 27 transaction, 6 security tests counted by Odoo) |
| ruff 0.16.0 check/format, py_compile, module wiring, circular deps, Odoo 19 XML, phantom-enum, manifest contract, BAN001 | pass |

Payable identity coverage and replay stability are asserted directly by the tests above (identity
reconciliation closing on every run; snapshot and census identical on replay after a blocked confirmation
recovers). Deferred, unchanged and not blocking: full SQL-backed first import, FK-level 561 census, full
second-run replay.

## 18. Session 6 (2026-10-10) — the reconciliation gap fails the run (GMP-004)

Contract: *GAR | PR #231 · GMP-004*, audited HEAD `b4a0ae8e7861fb766e8986275a1d350ce8b192fe`. Code commit
`e202417`. No ADR, mapping SSOT, chart seed, security file, business rule, summary schema, or other PR was
touched; BAN001 passes on all tracked content. Module versions `plasticos_transaction` 19.0.2.3.30,
`plasticos_partner_import` 19.0.2.10.20.

### 18.1 The defect at `b4a0ae8`

The identity reconciliation of §17.1 reported a gap as `report.anomaly("Payables", "reconciliation", …)`
only. Anomalies are diagnostics: `import_run_summary` never reads them, so the summary stayed `success` or
`partial` and `import_erp_shell.main()` returned 0. The one channel that did fail a run, `report.errors`,
is defined as *failed transaction units* and every entry is added to `records_rejected` and to the
`seen == created + updated + unchanged + rejected` equation; recording the reconciliation there would have
made the counters lie (one phantom rejected row, a spurious counter-reconciliation error) to balance a
check that is not a row.

### 18.2 The fix

| Layer | Change |
|---|---|
| `erp/report.py` | `ImportReport.failures` (`{check, detail}`) and `fail()`: a mandatory run-level check that did not pass. Not a row, never a counter, carried by `as_dict()` |
| `erp/summary.py` | each failure is projected into `errors` under its check name (`payables_reconciliation`), message capped at the contract's 2 000 characters, slots reserved beside the counter-reconciliation error ahead of the 1 000-row diagnostic cap; `final_status` is `failed` whenever a failure exists. `records_*` are untouched. New `run_exit_status(result, dry_run, layer)`: 1 on any run-level failure in every mode, 1 on a `failed` summary for an applied full run, 0 otherwise |
| `scripts/import_erp_shell.py` | `main()` prints each failure (`IMPORT FAILED: payables_reconciliation: …`) and returns `run_exit_status(...)`; a dry run or a layer run with a run-level failure no longer exits 0 |
| `models/native_document_import.py` | `realize()` calls `report.fail(PAYABLES_RECONCILIATION_REF, "payables identity reconciliation does not close: <gap>")` beside the existing anomaly. Nothing else changes: the census, `unresolved_bills`, the per-row dispositions and every counter are exactly those of GMP-003 |
| `scripts/run_erp_import.py` | the dry-run printout names run failures |

The shared summary schema (`contracts/schemas/draft/import-run-summary.schema.json`) is unchanged;
`validate_summary` passes on every projected failure. `tests/runtime_gates/run_erp_import.py` G1 still
expects `success`/`partial` on a closing run, which the positive path preserves.

### 18.3 Regression proof

| Tier | Test | Proves |
|---|---|---|
| pure python, `tests/test_erp_summary.py` | `test_a_run_level_failure_fails_the_run_without_touching_the_counters` | balanced report + one failure → `failed`, `records_seen` 4 = created 4, rejected 0, `errors` = the one failure, no counter-reconciliation error; the same report without the failure is `success` with identical `records_*` |
| | `test_an_omitted_or_blank_identity_payable_cannot_produce_a_successful_import` | the realizer's chain for an omitted identity ("1 missing PayableID: 591476") and a blank one ("1 source rows without a PayableID"): `payables_reconciliation` → `reconciliation_gap` → `report.fail` → summary `failed`, rejected 0 → `run_exit_status` 1 applied, dry run and layer; the closing counterpart exits 0 |
| | `test_run_exit_status_follows_the_summary_only_for_an_applied_full_run`, `…keep_their_slots_when_diagnostics_overflow`, `test_error_message_limit_matches_the_shared_contract` | exit matrix; 1 000 unresolved rows + failure keeps the failure's slot, rejected stays 1 000, message truncated to 2 000; the limit equals the schema's `maxLength` |
| pure python, `tests/test_erp_layer_gate.py` (real driver file, stubbed Odoo) | `test_a_run_level_failure_exits_nonzero_even_when_the_counters_close`, `test_a_dry_run_with_a_run_level_failure_exits_nonzero` | `main()` returns 1 and prints the failure on an applied run whose summary reads `success`, and on a dry run (no commit) |
| Odoo 19 runtime, `test_reconciliation_does_not_close_when_a_source_payable_is_on_neither_side` (extended) | blank-`PayableID` row end to end: `report.failures` = the one `payables_reconciliation` failure; projected summary `failed` with `records_rejected` 0 and every row `unchanged`; the closing run of the same worksheet projects `success`; `run_exit_status` 0 for the closing run, 1 for the failing run (applied and dry); `unresolved_bills` grew by exactly the one row |

### 18.4 Test results and gates

| Tier | Result |
|---|---|
| Pure python, whole repo | 1 115 passed, 48 skipped |
| Odoo 19 runtime, `/plasticos_transaction,/plasticos_security_base` on `erp_rt` | **0 failed, 0 errors of 29 tests** (`evidence/runtime_tests_gmp004.txt`) |
| ruff 0.16.0 check/format, py_compile, module wiring, circular deps, Odoo 19 XML, BAN001 | pass |

GMP-001/002/003 repairs, the F1–F6 protections, payable GL routing and the transaction-count rules are
unchanged (their tests are the same 29 runtime and 1 108 prior pure-python tests, all green). Deferred,
unchanged and not blocking: full SQL-backed first import, FK-level 561 census, full second-run replay.

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
| `runtime_tests_review_fixes.txt`, `mobile_probe.txt` | runtime re-verification after the PR review fixes (14 tests) and the `mobile` field probe |
| `run_import.sh`, `collect.sh`, `snapshot.sql`, `dump.sql` | exact commands to reproduce run 1 / run 2 and the normalised comparison |
| `runtime_tests_f5_census.txt` | session 2 Odoo 19 runtime result on the local nightly runtime (`0 failed, 0 errors of 19 tests`) |
| `grid_census.py`, `grid_census.txt` | session 2 source-side census on the frozen grid: order-link proxy, price precision as stored vs display, short-ton lines, payables routing by GL with vendors and dollars |
| `f7_environment_probe.txt` | session 2 proof that the ERP SQL Server source is not reachable from the session host (why run 1 / run 2 were refused) |
| `runtime_tests_gmp001.txt` | session 3 Odoo 19 runtime result after the accounting / quarantine convergence (GMP-001) |
| `runtime_tests_gmp002.txt` | session 4 Odoo 19 runtime result after the payable-coverage / disposition remediation (GMP-002) |
| `runtime_tests_gmp003.txt` | session 5 Odoo 19 runtime result after the identity-coverage / transaction-verdict remediation (GMP-003): 29 tests, 0 failed |
| `runtime_tests_gmp004.txt` | session 6 Odoo 19 runtime result after the fail-closed reconciliation remediation (GMP-004): 29 tests, 0 failed |
