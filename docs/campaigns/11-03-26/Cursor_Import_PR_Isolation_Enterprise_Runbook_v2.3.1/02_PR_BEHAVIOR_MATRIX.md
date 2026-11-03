## v2.3.0 machine-checkable test-to-claim binding

`BEHAVIOR_CATALOG.csv` is the precise execution checklist. Each row states the smallest **existing** test method, the expected observable result, whether a real Odoo method exists, and the coverage limit. Use the method ID rather than guessing from a `-k` substring. Do **not** create missing methods, weaken expectations, mark a missing assertion passed, or expand to logistics. For every row, record actual test ID/exit, corresponding log and SHA, verdict, and first wrong layer. When a test checks only AST/pure helper logic, mark its ORM counterpart `NOT_PROVEN`. If several rows share one Odoo module run, each still receives a separate evaluation.

The initial candidate inventory was derived from GitHub on 2026-10-24, not a permanent authorization: `Staging 2a3b9cda...`, open #301 `cc3f8cbb...`, open #303 `190c497...` (implementation baseline `702ebaf...`). Re-resolve before running. New or updated import PRs require a fresh behavior inventory; **never silently add a PR to the campaign, nor hot-swap its head**. Report a `SCOPE_CHANGE_REVIEW` to the operator and continue only the unaffected authorized lanes.

# 02. Per-PR, per-behavior verification matrix

**One PR = one immutable Git revision + isolated worktree + owned database clones + its own report. One behavior = one independently evaluated assertion or a documented coverage gap.** No aggregate PR PASS is permitted if any material behavior is FAIL/BLOCKED/NOT_PROVEN. A module execution may cover several behaviors, but each needs its own named method/probe evidence and verdict.

## Lane S: merged ERP/CRM imports on `Staging` (independent baseline)

These PRs are **already merged**, so use today's verified `Staging` revision, not their historical PR heads: #277 ERP/VS salespeople, #284 inbound inventory purchase, #291/#294 lead-vs-person call history, #295 active/inactive ERP contacts and VS field preservation, #298 PayablesBatch read-only census, and previously admitted material-profile work.

| ID | Behavior to prove | Existing pure/ORM owners | Distinguishing assertion | Failure classification |
|---|---|---|---|---|
| S-C1 | ERP company/contact identity and active/inactive aliases | `tests/test_erp_import_contract.py`, `tests/test_erp_source_layer.py`, `plasticos_partner_import/tests/` | No person or CT_ID alias from inactive source; no duplicate for approved person | `IDENTITY_LOSS`, `FALSE_ALIAS` |
| S-C2 | CRM approved crosswalk to an **existing** ERP person | `tests/test_crm_approved_identity.py`, `plasticos_crm_sync/tests/test_orchestrator_upsert.py` | Known approved ID uses ERP person; unknown does not fabricate link or second person | `CROSS_STREAM_IDENTITY` |
| S-C3 | Owner/salesperson semantics (#277) | `tests/test_vanillasoft_owner_crosswalk.py`, CRM Odoo tests | Tiffany login `sa@scrapmanagement.com`; unmapped owner does not overwrite existing seller | `OWNER_MAP` |
| S-C4 | Extra/disabled/duplicate phone, append-only notes (#295) | `tests/test_crm_approved_identity.py`, `tests/test_crm_sync_classification.py`, CRM Odoo tests | Disabled stays omitted; distinctions retained; existing ERP data untouched; replay doesn't append duplicates | `DATA_LOSS_OR_OVERWRITE` |
| S-C5 | Call and custom history owned by correct lead or person (#291/#294) | `tests/test_crm_history_links.py`, CRM Odoo tests | Bound person owns history; lead-only history stays lead-only; stale refs fail closed | `HISTORY_OWNERSHIP` |
| S-C6 | Full/incremental CRM history and truthful status | `tests/test_crm_sync_full_import.py`, `tests/test_crm_sync_completeness.py`, F1-F3 runtime gate | Explicit historical floor, no false-complete run, correct watermark, archive/restore semantics | `FALSE_SUCCESS_OR_WATERMARK` |
| S-M1 | Material/polymer/form and nullable form | `plasticos_material_profile/tests/test_material_normalizer.py`, `test_nullable_form_uniqueness.py` | Exact profile identity, no invented taxonomy, idempotent reuse | `MATERIAL_IDENTITY` |
| S-E1 | Inbound purchase to inventory without sale (#284) | `tests/test_erp_source_layer.py`, `plasticos_transaction/tests/test_erp_worksheet_import.py` | Existing PO and warehouse, no fabricated sale/stock event; ambiguous warehouse held | `COMMERCIAL_GRAPH` |
| S-E2 | PayablesBatch rows/headers and PrePay exclusion (#298) | `tests/test_erp_source_layer.py`, `tests/test_erp_mapping_status.py` | Index/census truthful for multi-row batch, duplicates/NULL/currency; no new bill ownership | `SOURCE_OR_ACCOUNTING_IDENTITY` |
| S-E3 | Import outcomes and reconciliation | `tests/test_erp_summary.py`, `tests/test_erp_layer_gate.py`, `tests/test_erp_import_limit.py` | Source row identity accounted, no misleading success with unaccounted payables/contacts | `FALSE_SUCCESS` |

**Testing limit:** The existing `Staging` transaction runtime suite does **not** cover every root `tests/` Odoo test that PR #303 later proposes to relocate. A passing baseline module test is not evidence that a root test silently ran. Mark root test cases `NOT_COLLECTED` until proved otherwise.

## Lane 301: [PR #301](https://github.com/cryptoxdog/IB-Odoo_19/pull/301), independent PR head

This PR is not merged into the baseline at the observed snapshot. It modifies `plasticos_partner_import` and `plasticos_transaction`, not VanillaSoft. Verify its delta **against its own parent Staging**, using only #301's exact head. Source helpers run in pure pytest, runtime effects under the existing Enterprise fixture, with module scope `plasticos_transaction`.

| ID | #301 behavior | Smallest existing pure test | Named Odoo runtime assertion(s) | Require independent evidence of |
|---|---|---|---|---|
| 301-A | `PayablesBatch` header invoice date/reference wins; row fallback when no header | `tests/test_erp_native_orders.py::test_vendor_bill_takes_its_batch_header_facts`, `::test_vendor_bill_without_a_header_keeps_its_row_facts_and_no_due_date` | `TestErpWorksheetImport.test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event` | Exact invoice dates + `ref`; one bill per `PayableID`; no worksheet-order-date fallback |
| 301-B | Named existing AP payment term vs explicit header DueDate | `tests/test_erp_native_orders.py::test_matched_term_applies_only_to_a_dated_bill`, `::test_unmatched_term_uses_the_header_due_date_and_clears_the_default_term` | Same first Odoo test; audit both cases separately | Dated + matched term computes correctly; unmatched term doesn't inherit supplier default |
| 301-C | Undated bill cannot invent import-day-dependent maturity | `tests/test_erp_native_orders.py::test_vendor_bill_with_no_source_invoice_date_gets_none_and_ref_falls_back_to_the_payable`, `::test_matched_term_applies_only_to_a_dated_bill` | Coverage of undated **vendor** bill must be individually verified, not assumed from an undated customer invoice test | Undated header due date preserved; missing date/terms not silently invented |
| 301-D | Earliest `GPLedger.TradeDt` becomes PO approval date | `tests/test_erp_native_orders.py` source-date logic and `tests/test_erp_native_document_guard.py` | First Odoo test for dated trade; second for missing trade | Deterministic earliest date; missing trade date yields exact anomaly and no fabricated date |
| 301-E | Unknown `Delivered` basis not falsely labelled FAS | `tests/test_erp_native_orders.py::test_delivered_basis_is_declined_not_mapped_to_fas` | `TestErpWorksheetImport.test_delivered_basis_sets_no_incoterm_and_undated_invoice_stays_undated` | No incoterm + explicit anomaly; known FAS remains FAS |
| 301-F | Historical sale confirmation must not create deliveries or stock | `tests/test_erp_native_document_guard.py::test_sale_confirmation_launches_no_procurement` plus forbidden-call/model guards | First Odoo test's `picking_ids`, stock.picking/stock.move counts | `skip_procurement`, no phantom logistics stock event from ERP import (not a logistics feature test) |
| 301-G | Customer invoice lacking source invoice date stays undated | `tests/test_erp_native_orders.py` date helper checks | Second Odoo test, assertion on `invoice_date` and anomaly | No fallback to current day or `BuySell.OrderDt` |
| 301-H | Odoo documents remain draft, no payment/posting | `tests/test_erp_native_document_guard.py` | First Odoo test: account.move states and PO draft | No event or financial action invented |

**Important coverage caveat:** The two new Odoo methods do not automatically prove the specific *undated vendor bill with a source header DueDate* path. If no existing runtime test asserts that combination, mark `301-C ORM = NOT_PROVEN`; do not author a test or patch it without approval. The pure helper can still PASS independently. Every `301-A` through `301-H` gets its own verdict, even if all use one Odoo module execution.

## Lane 303: [PR #303](https://github.com/cryptoxdog/IB-Odoo_19/pull/303), independent discovery/behavior PR

This PR reports relocating 39 previously orphaned root `tests/` Odoo modules into owning addons. It also contains **real non-test changes** to document compliance, transactions, matching, and logistics. Therefore **never treat it as a test-only patch or combine it with #301**. Its reported Community tests are not Enterprise acceptance; this campaign runs only on the already-admitted Enterprise template, and excludes Linda/logistics test cases.

| ID | #303 import-relevant behavior | Where to look (on #303 only) | Signal |
|---|---|---|---|
| 303-A | Root Odoo tests are no longer orphaned; addon tests are imported by `tests/__init__.py` | `tests/test_odoo_test_discovery.py` + relevant addon test registrations | Registered module paths resolve; no silent zero-test green |
| 303-B | ERP import's test discovery and retired CSV path | `plasticos_partner_import/tests/test_partner_import_csv_paths.py` | Test actually **runs** under `plasticos_partner_import` on Enterprise |
| 303-C | Transaction integration tests are discoverable | `plasticos_transaction/tests/test_transaction_contracts.py`, `test_sale_order_transaction_autocreate.py`, `test_bridge_wiring_contracts.py` | Actual method invocation + pass/fail at exact #303 SHA |
| 303-D | CRM core/partner mapping test classes are discovered | `plasticos_base/tests/test_crm_lead_contracts.py`, `test_partner_contracts.py` | Their exact tests run; not just registered via imports |
| 303-E | Material-profile contract and polymer tests are discoverable | `plasticos_material_profile/tests/test_material_profile_intake_delta_contract.py`, `test_polymer_product_sync.py` | Exact method IDs + assertion results; avoid logistics/matching unrelated tests |
| 303-F | Invoice/transaction document gate remains functionally correct where the import path uses it | `plasticos_documents/tests/test_account_move_transaction_link.py`, `test_compliance_service.py`, PR delta in `models/compliance_service.py`, `plasticos_transaction/models/account_move_inherit.py` | Distinguish corrected silent skip from new business-blocking rule; **operator decision required** for altered document policy |

**Known author-reported results, not independently accepted:** A Community run of #303 reportedly ended with 7 failures and 1 error out of 807. Known classes include claims, offer association, ACL permissions and a Community accounting-template gap in `TestErpWorksheetImport`. Do **not** repair these or convert them into false blockers for #301. If they demonstrably affect an import-owned path in #303, report that exact effect; otherwise mark `OUTSIDE_IMPORT_SCOPE` and preserve as informational.

**Excluded in #303:** `plasticos_logistics/*`, tests of Linda freight/load flows, claims/offer security redesign, blanket ACL remediation and matching-engine product changes. Required preexisting dependency installation by the fixture is not an endorsement of that functionality. A test requiring a logistics-specific setup is `OUT_OF_SCOPE` and stops, rather than expanding the mission.

## Cross-PR interpretation rule

- `S` PASS proves only the currently merged baseline at its SHA.
- `301` PASS proves only #301's code on its own parent/fixture; not #303 code.
- `303` PASS proves only #303's code on its own parent/fixture; not #301 code.
- #301 and #303 both touch `plasticos_transaction` and both propose manifest `19.0.2.3.40`. Record `INTEGRATION_OVERLAP: UNTESTED`, do not merge the branches, bump a version or pick a winner.
- The eventual combined integration SHA, if ever authorized, requires **another** targeted regression run. No agent may assume the current independent results transfer across a merge.

## Final lane I: operator-approved integrated CRM + ERP import revision (after all individual fixes pass)

This is a **new future phase**, not a fourth PR to be merged by Cursor. Use the exact approved integrated SHA/ref only, after the operator accepts the independent PR results and all remedial fixes. Execute `06_FINAL_COHESION_GATE.md` and record each of these separately.

| ID | Cross-system property | Testable evidence / why it matters | Strict verdict limit |
|---|---|---|---|
| I-A | Source and approved delta closure | 40-hex combined SHA; operator approval; PR/fix-to-integration mapping; clean isolated checkout; no unapproved scope | Wrong or missing integrated code = BLOCKED, never PASS |
| I-B | CRM + ERP reader/mapping contract compatibility | Source/crosswalk, header-facts, material, call-history and report pure tests **on combined SHA** | Pure tests do not prove ORM persistence |
| I-C | Import addons load and test together | One guarded Enterprise module invocation on one fresh clone for import-facing modules; individually proven registered assertions | Same registry is proven, not yet same persisted business data |
| I-D | Full CRM state/watermark replay still works | F1-F3 synthetic real Odoo/Postgres gate, receipt named for combined SHA | Its dedicated clone is separate from ERP data; do not call this integrated ERP+CRM replay |
| I-E | ERP people stay unique when VanillaSoft history/materials land | **Same disposable clone** after ERP then CRM import, exact partner/external identity links and field precedence | Requires explicit applied-test-import authority; otherwise NOT_PROVEN |
| I-F | Commercial documents preserve source dates, terms, quantity, inventory and no phantom financial/stock events | **Same disposable clone**, reconciled source identities/amounts and native Odoo fields | Accepted draft/posted policy vs business fidelity must be distinguished |
| I-G | ERP + CRM replay is idempotent as one graph | Both imports repeated against **the same clone**, stable identities, no duplicate notes/history, reconciling totals and truthful summary | Missing safe source/harness/authorization = NOT_PROVEN/BLOCKED; never implied by I-C |

`COMBINED_RUNTIME_PASS` means I-A through I-D are supported and I-E through I-G are explicitly unproven or blocked. `COHESION_PASS` requires **I-A through I-G** all independently demonstrated at one integration SHA, with approved source-to-ORM meaning. Never award a top-line PASS from a combined test count alone. Exclude Linda/logistics behavior throughout.

## v2.3.1: published evidence requirements for lane 303

The authoritative frozen executable baseline is `702ebaf77d987dc844e2758bd354b2ecef4f26cd`; the **exact checkout and receipt must use** PR head `190c497bdea1362cad87e231c713efdcd25240d4` unless GitHub changed again. The new commit adds only five handoff documents, so existing CE failures remain agent-reported until an independent Enterprise run proves otherwise. See `10_PR303_PUBLISHED_HANDOFF_ACCEPTANCE.md` and the 10 `303-DIAG-*` rows in `BEHAVIOR_CATALOG.csv` (diagnostic inventory, not blanket permission to run excluded modules).

The known seven cannot be deleted, skipped, weakened or reclassified as passing. Correct classification is 2 claim-margin `BUSINESS_SEMANTICS_UNRESOLVED`; 2 obsolete offer-acceptance assertions with accepted state-only workflow; 3 ACL security exposures requiring role policy. If the result changes on Enterprise, investigate the change rather than silently marking success. `TestErpWorksheetImport` XMLID error is a separate Enterprise fixture hypothesis; `TestTransactionACL.test_base_user_cannot_unlink` unexpectedly passed on CE and requires an **actual AccessError origin**, not speculation. Closing/auto-post compliance must be investigated as a workflow risk, with no accounting writes beyond the owned test clone.
