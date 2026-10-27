# PR #303: failures, scope inventory, open risks, Enterprise validation requirements

**Baseline under test:** `702ebaf77d987dc844e2758bd354b2ecef4f26cd` (head of `claude-mobile/eloquent-wright-4yz1u4`). The documentation commit that adds this directory changes no code or tests.
**PR base:** `Staging` @ `2a3b9cda9b127c284d12f98bf35ab0344a500d10`.

Everything in §1 and §3 is **OBSERVED (CE runtime)**: a local **Odoo 19.0 Community** runtime, **not** the admitted Enterprise fixture. Community results are not Enterprise proof.

## 1. Known failures (7 failed, 1 error) — keep visible

**Final CE run:**
- Scope: every installed `plasticos_*` addon (template excluded `plasticos_documents_native`, `plasticos_semantic_kernel` and non-installable addons).
- Command: `--test-enable --test-tags /<each installed plasticos addon> --stop-after-init --log-level=test`, on a disposable clone of a template DB.
- Odoo summary line: `odoo.tests.result: 7 failed, 1 error(s) of 807 tests`.
- No pre-existing (non-moved) addon test regressed.

| # | Test ID | File:line | Classification |
|---|---|---|---|
| 1 | `TestTransactionClaimsBridgeDepends.test_freight_chargeback_recovery_flows_to_transaction` (expected 125.0, got 0.0) | `plasticos_claims/tests/test_depends_transaction_claims_bridge.py:75` | BUSINESS_SEMANTICS_UNRESOLVED (Decision A) |
| 2 | `TestTransactionClaimsBridgeDepends.test_lightweight_penalty_recovery_flows_to_transaction` (expected 75.0, got 0.0) | `plasticos_claims/tests/test_depends_transaction_claims_bridge.py:84` | BUSINESS_SEMANTICS_UNRESOLVED (Decision A) |
| 3 | `TestOfferBridge.test_offer_accept_creates_transaction` | `plasticos_claims/tests/test_bridge_models.py:51-58` | Obsolete assumption; test unchanged (Decision B) |
| 4 | `TestOfferActions.test_action_accept_creates_transaction` | `plasticos_security_base/tests/test_action_methods.py:341-346` | Obsolete assumption; test unchanged (Decision B) |
| 5 | `TestClaimACL.test_claim_user_cannot_unlink` (`AccessError` not raised) | `plasticos_commission/tests/test_security_acl.py:145-148` | ACL exposure; role policy required (Decision C) |
| 6 | `TestClaimACL.test_no_group_cannot_read` (`AccessError` not raised) | `plasticos_commission/tests/test_security_acl.py:155-158` | ACL exposure; role policy required (Decision C) |
| 7 | `TestTransactionACL.test_base_user_cannot_write_tx_line` (`AccessError` not raised) | `plasticos_commission/tests/test_security_acl.py:59-63` | ACL exposure; role policy required (Decision C) |
| E | `TestErpWorksheetImport` setUpClass: `ValueError: External ID not found in the system: plasticos_accounting.account_40050_sales_income` | `plasticos_transaction/tests/test_erp_worksheet_import.py:123` (pre-existing, not moved, not edited by #303) | **Unverified environment hypothesis** (§2) |

**CE run history** (Odoo summary lines):

| Stage | Scope | Result |
|---|---|---|
| After relocation, before repairs (`7fb71df`) | 14 owning addons | `34 failed, 135 error(s) of 621 tests` |
| After test/fixture repairs and the logistics + matching fixes | 14 owning addons | `8 failed, 2 error(s) of 692 tests` |
| Final, after the golden-flow repair and compliance-gate change (`702ebaf`) | every installed plasticos addon | `7 failed, 1 error(s) of 807 tests` |

## 2. `TestErpWorksheetImport`: unverified environment hypothesis

- **OBSERVED (CE):**
  - In the local template, `account_account` had no `40050`/`50100` rows and `ir_model_data` held no `plasticos_accounting` `account.account` XML IDs. Only payment terms were present, although `plasticos_accounting` reported `installed`, `l10n_us` was installed and the company chart was `generic_coa`.
  - The same setUpClass error appears in the run before any production change, so it is not caused by #303's code changes.
- **OBSERVED (CE):** on a disposable copy of that template, `-u plasticos_accounting` alone created `account_40050_sales_income`, `account_40075_tax_refund` and `account_50100_material_cost` (`ir_model_data` rows present afterwards).
- **HYPOTHESIS:** in the local fresh install, `plasticos_accounting` (`auto_install`, depends only on `account`) loaded `data/accounts.xml` in the same `-i` as `account` and its chart template, and the accounts did not survive that sequence. The test code is not the cause.
- **Not verified on Enterprise.** Decision E: establish whether the test passes **with the seeded accounting records present**, without modifying or reseeding the Enterprise template.
- **PR #301 interaction:** #301 edits this same file (adds `test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event`). Testing #303 alone does not cover #301's version of it.

## 3. Per-file results for the 39 relocated test modules — OBSERVED (CE)

Counts are transcribed from the final CE run (§1, `702ebaf`). Across the relocated modules **605 tests ran and 7 failed**. The remaining 202 of the 807 tests are pre-existing addon tests, all passing except `TestErpWorksheetImport`.

| New location | Old location | Ran | Pass | Fail/Err |
|---|---|---:|---:|---:|
| `plasticos_base/tests/test_crm_lead_contracts.py` | `tests/contracts/` | 6 | 6 | 0 |
| `plasticos_base/tests/test_partner_contracts.py` | `tests/contracts/` | 11 | 11 | 0 |
| `plasticos_base/tests/test_xpath_field_refs.py` | `tests/` | 1 | 1 | 0 |
| `plasticos_claims/tests/test_bridge_models.py` | `tests/` | 22 | 21 | 1 (#3) |
| `plasticos_claims/tests/test_constraints_onchanges.py` | `tests/` | 28 | 28 | 0 |
| `plasticos_claims/tests/test_cron_idempotency.py` | `tests/integration/` | 15 | 15 | 0 |
| `plasticos_claims/tests/test_cron_plasticos_base.py` | `tests/` | 18 | 18 | 0 |
| `plasticos_claims/tests/test_cron_runtime.py` | `tests/` | 10 | 10 | 0 |
| `plasticos_claims/tests/test_depends_transaction_claims_bridge.py` | `tests/` | 5 | 3 | 2 (#1, #2) |
| `plasticos_claims/tests/test_integration_flows.py` | `tests/` | 8 | 8 | 0 |
| `plasticos_claims/tests/test_selection_contracts.py` | `tests/contracts/` | 6 | 6 | 0 |
| `plasticos_claims/tests/test_state_machines.py` | `tests/` | 48 | 48 | 0 |
| `plasticos_commission/tests/test_api_signature_contracts.py` | `tests/contracts/` | 5 | 5 | 0 |
| `plasticos_commission/tests/test_constraint_validation.py` | `tests/` | 8 | 8 | 0 |
| `plasticos_commission/tests/test_golden_flows.py` | `tests/` | 20 | 20 | 0 |
| `plasticos_commission/tests/test_security_acl.py` | `tests/` | 20 | 17 | 3 (#5, #6, #7) |
| `plasticos_documents/tests/test_account_move_transaction_link.py` | `tests/integration/` | 13 | 13 | 0 |
| `plasticos_documents/tests/test_compliance_service.py` | `tests/integration/` | 10 | 10 | 0 |
| `plasticos_intake/tests/test_computed_field_deps.py` | `tests/contracts/` | 6 | 6 | 0 |
| `plasticos_intake/tests/test_intake_contracts.py` | `tests/contracts/` | 42 | 42 | 0 |
| `plasticos_intake/tests/test_intake_onchange_cascade.py` | `tests/integration/` | 8 | 8 | 0 |
| `plasticos_intake_normalizer/tests/test_cron_batch_normalize.py` | `tests/` | 10 | 10 | 0 |
| `plasticos_logistics/tests/test_linda_freight_models.py` | `tests/integration/` | 17 | 17 | 0 |
| `plasticos_matching/tests/test_match_result_guards.py` | `tests/integration/` | 14 | 14 | 0 |
| `plasticos_matching/tests/test_performance.py` | `tests/` | 7 | 7 | 0 |
| `plasticos_material_profile/tests/test_constraints_material_profile.py` | `tests/` | 2 | 2 | 0 |
| `plasticos_material_profile/tests/test_material_profile_intake_delta_contract.py` | `tests/contracts/` | 6 | 6 | 0 |
| `plasticos_material_profile/tests/test_polymer_product_sync.py` | `tests/integration/` | 5 | 5 | 0 |
| `plasticos_offer/tests/test_offer_state_machine.py` | `tests/integration/` | 23 | 23 | 0 |
| `plasticos_offer/tests/test_write_unlink_guards.py` | `tests/integration/` | 8 | 8 | 0 |
| `plasticos_order_lines/tests/test_onchange_purchase_order_line_plasticos.py` | `tests/` | 3 | 3 | 0 |
| `plasticos_order_lines/tests/test_onchange_sale_order_line_plasticos.py` | `tests/` | 3 | 3 | 0 |
| `plasticos_partner_import/tests/test_partner_import_csv_paths.py` | `tests/` | 14 | 14 | 0 |
| `plasticos_security_base/tests/test_action_methods.py` | `tests/` | 75 | 74 | 1 (#4) |
| `plasticos_security_base/tests/test_bridge_contracts.py` | `tests/` | 73 | 73 | 0 |
| `plasticos_security_base/tests/test_error_handling.py` | `tests/` | 14 | 14 | 0 |
| `plasticos_transaction/tests/test_bridge_wiring_contracts.py` | `tests/contracts/` | 6 | 6 | 0 |
| `plasticos_transaction/tests/test_sale_order_transaction_autocreate.py` | `tests/integration/` | 4 | 4 | 0 |
| `plasticos_transaction/tests/test_transaction_contracts.py` | `tests/contracts/` | 11 | 11 | 0 |

Skips that remain in these files are pre-existing guards; none were added.

**Pure-Python tier (pytest, no Odoo)** — OBSERVED:
- Base and head collect the identical 1842 test IDs, plus the 4 new guard tests in `tests/test_odoo_test_discovery.py`.
- Local result: `1797 passed, 49 skipped`.
- GitHub `ci.yml` (`CI Gate Result`) is green, but it does **not** run Odoo runtime tests.

## 4. PR #303 scope inventory (`2a3b9cd..702ebaf`, 9 commits)

| Category | Contents |
|---|---|
| **1. Test discovery and registration** | 39 `git mv` relocations, content unchanged at move (`7fb71df`). 14 addon `tests/__init__.py` (5 new). 10 `.gitkeep` removed. Guard `tests/test_odoo_test_discovery.py`. `tests/README.md`. Path pointers in `TODO.md`, `docs/adr/ADR-005-…`, `docs/adr/ADR-008-…`, `.coderabbit.yaml`, the `tests/test_legacy_import_ui_retired.py` docstring. The missing `PlasticosTestCase` import in `test_intake_onchange_cascade.py`, which aborted the registry at suite load |
| **2a. Test corrections: Odoo 19 API** | `group_ids` (was `groups_id`), `registry.field_depends`, Selection `get_values()`, `mail.thread._inherit_children`, removed `product_id_change` (now driven through `Form`), single-class `assertRaises` / `IntegrityError` / `CheckViolation`, patching the `config` object |
| **2b. Test corrections: changed PlasticOS contracts** (not Odoo 19; this is the larger share) | Claim, load, intake and transaction state and method names. Removed fields (`buyer_partner_id`, `summary`, …). Gate-only matching and enrichment. Required-field and freight-context fixtures. **New tests:** 3 unmocked compliance-gate tests (`plasticos_documents/tests/test_account_move_transaction_link.py`), 1 bulk-cancel-wizard test (`plasticos_transaction/tests/test_transaction_contracts.py`) |
| **3. Production behaviour changes** | `plasticos_documents/models/compliance_service.py` and `plasticos_transaction/models/account_move_inherit.py` + `transaction.py`: the invoice-post and close document gates now run, purpose-scoped by `required_for_invoice` / `required_for_close`. Closing requires required-for-close documents (seeded: verified scale ticket). Versions `plasticos_documents` 19.0.2.1.2, `plasticos_transaction` 19.0.2.3.40.<br>`plasticos_matching/models/match_exclusion.py`: `ValidationError` import, so a validation message instead of `AttributeError`. Version 19.0.3.1.4 |
| **4. Logistics** (outside the CRM/ERP campaign) | **Production:** `plasticos_logistics/models/freight_governance.py`, which drops `required` on `facts`/`unknowns` (the upgrade drops NOT NULL) and takes the transaction company from its sale order. Version 19.0.1.10.4.<br>**Tests:** `plasticos_logistics/tests/test_linda_freight_models.py` registered (+ fixture). Load-lifecycle test edits in `plasticos_claims` (`test_state_machines`, `test_integration_flows`, `test_selection_contracts`), `plasticos_security_base` (`TestLoadActions`, `TestLoadModelContract`) and `plasticos_commission` (`TestGoldenLeadToDelivery`) |

**Decision D:** categories 3 and 4 are earmarked for future scope separation. Nothing is split, reverted or modified yet.

**Coupling:** if the freight fix leaves #303, about 40 load-lifecycle tests on #303 revert to `NotNullViolation` failures: 16 Linda, 15 claims, 8 security_base and 1 golden flow. Either their registration moves with the fix, or they stay visibly red.

## 5. Open risks

1. **Document compliance × automatic invoice posting** (unanalysed, unapproved).
   - `_compute_compliance` (`plasticos_transaction/models/transaction.py:852-877`) uses the **unscoped** `is_compliant`. It calls `_auto_post_pending_invoices` (`:879-898`) on a `missing` → `compliant` change.
   - That path runs `account.move.action_post()`, whose gate #303 now enforces with `purpose="invoice"`.
   - The two compliance notions (unscoped status vs. purpose-scoped gates) can diverge.
   - Also, `action_close` now blocks without required-for-close documents, which could stop closings on Staging data that lacks scale tickets.
2. **Version collision.**
   - #301 (`claude/new-session-bd26s3` @ `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79`) and #303 both set `plasticos_transaction` to `19.0.2.3.40`.
   - Identical edits merge cleanly, so the second PR could land without a version advance and its code would not reload.
   - Resolve only during approved integration; the final version must exceed the installed one and the upgrade must be verified.
3. **Overlapping modules.** #301 and #303 both touch `plasticos_transaction` (manifest; #301 also edits `tests/test_erp_worksheet_import.py`). They are independent branches and are not combined for testing.
4. **Odoo.sh visibility.** Odoo.sh `--test-enable` builds now execute the relocated tests, so the 7 known failures will appear there.
5. **Install-smoke not run.** Published with `make pr-nosmoke` (no `odoo-enterprise` checkout in the cloud container). `plasticos_documents_native` was not exercised.
6. **Unexpected PASS.**
   - `TestTransactionACL.test_base_user_cannot_unlink` raised `AccessError` in CE although `access_transaction_all` grants delete to `base.group_user`.
   - The mechanism is unidentified (see `security-acl-brief.md` §3).

## 6. Enterprise validation requirements (Cursor; Decision E)

1. Test **#303 at `702ebaf77d987dc844e2758bd354b2ecef4f26cd`** (or this documentation commit, whose code is byte-identical), and **#301 at its own exact SHA, separately**. Never combine the branches.
2. Use the existing admitted Enterprise fixture (`config/test_env_fixture.conf`: `odoo_test_tpl_ee_c9e8a81f52f23680`) through owned disposable clones. Do not modify or reseed the template.
3. Upgrade only the modules #303 bumps: `plasticos_logistics`, `plasticos_matching`, `plasticos_documents`, `plasticos_transaction`.
4. Run the relocated tests' owning addons:
   - `/plasticos_base`, `/plasticos_claims`, `/plasticos_commission`, `/plasticos_documents`, `/plasticos_intake`, `/plasticos_intake_normalizer`, `/plasticos_logistics`
   - `/plasticos_matching`, `/plasticos_material_profile`, `/plasticos_offer`, `/plasticos_order_lines`, `/plasticos_partner_import`, `/plasticos_security_base`, `/plasticos_transaction`
   - Plus `plasticos_documents_native`, which only Enterprise can exercise.
5. Confirm on Enterprise:
   - whether exactly the 7 failures in §1 reproduce, and whether anything else fails
   - whether `TestErpWorksheetImport` passes with the seeded accounting records present (check `ir_model_data` for `plasticos_accounting.account_40050_sales_income` in the clone)
   - the mechanism behind the `test_base_user_cannot_unlink` `AccessError`
6. Report Odoo `odoo.tests.result` summary lines and failing test IDs per PR, per SHA.
7. **The final cohesive-system run requires separate operator authorization.**
