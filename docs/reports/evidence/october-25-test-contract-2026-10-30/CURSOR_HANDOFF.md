# Handoff: October 25 test contract, then the blocked security closure

**Date:** 2026-10-30
**Pull request:** https://github.com/cryptoxdog/IB-Odoo_19/pull/347
**Test-contract commit:** `9a5785741cb34062912766ea9eefe9acd59fe9e0`
**Base:** `Staging` at `42556d2e` (merge of PR #342)
**Branch:** `test/align-october-25-contract`
**Worktree:** the sibling checkout created for this publication. The original workspace is still `Staging` and is dirty with unrelated campaign files. Do not run `make commit` or `make pr` there.

This publication contains the approved test-contract alignment only. It does not change ACL rows, claim creation, the CSV wizard, manifests, or production Python.

## What this branch changes

Four test files. No module version bump. Tests and docs do not reload a running database.

| File | Change |
|---|---|
| `plasticos_claims/tests/test_bridge_models.py` | `test_offer_accept_creates_transaction` is now `test_offer_accept_leaves_transaction_unlinked`. `test_transaction_links_back_to_offer` is now `test_offer_accept_does_not_link_a_transaction`. |
| `plasticos_security_base/tests/test_action_methods.py` | `test_action_accept_creates_transaction` is now `test_action_accept_leaves_transaction_unlinked`. |
| `plasticos_security_base/tests/test_bridge_contracts.py` | Docstrings only: `transaction_id` exists and acceptance does not write it; `action_accept` changes state only; claim case types do not compute transaction amounts. |
| `plasticos_claims/tests/test_depends_transaction_claims_bridge.py` | Freight and lightweight tests prove a manual `40.0` survives resolve (`125.0` / `75.0` on the claim) and archive. The unresolved test proves `500.0` on an open claim leaves `40.0` on the transaction. |

`test_offer_reject_no_transaction`, `test_action_accept`, `test_action_view_transaction`, `test_claim_ids_and_count_track_new_claims`, and `test_has_quality_claim_set_and_cleared_by_state` were left as they were.

The three ACL tests in `plasticos_commission/tests/test_security_acl.py` were not edited. They stay red on purpose.

## Contract this branch pins

Operator decision 2026-10-25, PR #303:

- `action_accept` writes only `state`, `accepted_by`, and `accepted_date`.
- A live transaction is created in `sale.order.action_confirm` when `order.transaction_id` is empty (`plasticos_transaction/models/sale_inherit.py`).
- `offer.transaction_id` exists. Nothing in production writes it during accept. `plasticos.transaction` has no `offer_id`.
- `freight_chargebacks` and `lightweight_penalties` stay plain floats. `_compute_chargebacks_penalties` is dead code and must not be wired. A resolved claim is not a booked credit.
- Do not add automatic transaction creation, stored recovery computes, or a financial backfill.

## Enterprise results already observed

Fixture: `config/test_env_fixture.conf`, template `odoo_test_tpl_ee_c9e8a81f52f23680`, clone `odoo_test_w2495f48767`.

`make test-module m=plasticos_claims,plasticos_security_base`: 343 tests, 0 failed, 2 errors. The six renamed methods passed. The two errors are pre-existing and are not in this commit:

- `TestCronInDomain.test_scale_tickets_leave_unloaded_transaction` — `AttributeError: load_id`. The field is retired. Cardinality is `load_ids`.
- `TestCronInDomain.test_compliance_audit_clears_verified_on_expired_document` — `AccessError: Business verification cannot be written directly.` The cron logs expired verified documents and does not clear `verified`.

`make test-module m=plasticos_commission`: 71 tests, 3 failed, 0 errors. The failures are exactly:

- `TestClaimACL.test_claim_user_cannot_unlink`
- `TestClaimACL.test_no_group_cannot_read`
- `TestTransactionACL.test_base_user_cannot_write_tx_line`

Each failed with `AssertionError: AccessError not raised`. `test_claim_manager_can_unlink` and `test_manager_can_write_tx_line` passed. `test_base_user_cannot_unlink` passed because unlink reads `account.move` and the internal user cannot read that model. That pass is not proof that `access_transaction_all` is safe. That row is the only unlink grant on `plasticos.transaction`. The manager row is `1,1,1,0`.

## Do not start the security edit until these are answered

A read-only pass on 2026-10-30 rechecked the clone. Installed ACL rows match the CSVs, `noupdate` is false, and there is no XML-id-less extra row. The local `odoo` database has no tables. The template does not accept connections.

Proposed boundaries, not yet approved as an edit:

- Claims User and Claims Manager for claim access.
- Claims Manager only for pending-claim deletion.
- Transaction Manager for transaction-line mutation.
- Ordinary internal users must not get claim CRUD or transaction-line write through `base.group_user` blankets.

Two installed grants conflict with that proposal. Report them again if the operator has not answered.

1. **Logistics line write stays after the blanket is removed.** `plasticos_security_base/security/ir.model.access.csv` row `access_transaction_line_logistics` is `1,1,1,0`. Do not delete or narrow it until the operator says logistics loses line create/write.
2. **Settings inherits Transaction Manager and does not inherit Claims Manager.** On the clone, `base.group_system` implies `plasticos_transaction.group_plasticos_manager`. It does not imply `plasticos_claims.group_claims_manager`. The only direct claims-manager member is `system_cron`. `plasticos_base/hooks.py` intends an admin grant that this clone does not show for `admin` or the scrap-management logins. Removing `access_claim_all` drops Settings users out of claims unless that membership is confirmed on the target database.

Also unresolved, and each one blocks part of the Claim Pics path:

3. `plasticos.claim` has no `company_id` and no uploader field. `create_uid` would become the superuser if the create is privileged. A new `reported_by_id` is a schema change and was not approved.
4. Company resolution is `_resolved_subject_company`, which refuses `env.su`. Do not call `document.sudo()`.
5. `source_document_id` is not unique. Search-then-create can race.
6. `test_claim_pictures_keep_the_exact_subject` expects the claim at document create, before association is accepted. Gating on company and association changes that test.

Do not remove `access_transaction_all` in the same change as the line and claim blankets.

## File-level proposal, still not applied

| File | Proposed change |
|---|---|
| `plasticos_claims/security/ir.model.access.csv` | Remove `access_claim_all` and `access_claim_bulk_wizard_all`. Keep the claims user and claims manager rows. |
| `plasticos_transaction/security/ir.model.access.csv` | Remove `access_transaction_line_all` and, with the wizard retirement, `access_transaction_import_wizard_user`. Leave `access_transaction_all`. |
| `plasticos_security_base/security/ir.model.access.csv` | Unchanged until logistics line write is explicitly withdrawn. |
| `plasticos_claims/models/claim.py` | Add `plasticos.claim._create_for_claim_document(document)`, called only from `_check_claim_trigger`. Refuse when `document.env.su`. Create nothing on a subject conflict, an empty transaction, a company error, or a company outside `env.user.company_ids`. Lock and search one `source_document_id`. The privileged write is that one create only. |
| `plasticos_claims/models/document_inherit.py` | Call that method instead of `claim.create` on the uploader. |
| `plasticos_transaction/views/transaction_import_wizard_views.xml` | Remove `menu_transaction_import_wizard` and `action_transaction_import_wizard`. The menu is active and has zero groups. |
| `plasticos_transaction/wizards/transaction_import_wizard.py` | `action_import` raises a retirement error. Do not add an importer group. |
| `plasticos_transaction/models/transaction_import_service.py` and `scripts/run_transaction_import.py` | Leave them. They are the shell path and are documented as legacy in `plasticos_transaction/README.md`. ERP import does not write these lines. |
| Manifests | Bump `plasticos_claims` and `plasticos_transaction` only when those runtime files change. Then `make update m=` those modules only. |

Sibling blankets that were not authorized for deletion: `access_transaction_bulk_wizard_user`, `access_transaction_bulk_assign_wizard_user`, `access_audit_cron_all`.

## Negative tests to add only with the ACL edit

Keep the three current failures as the assertions. Do not `xfail` them.

| Test | Actor | Expected |
|---|---|---|
| `test_no_group_cannot_read` | Internal User | `AccessError` on claim read |
| `test_claim_user_cannot_unlink` | Claims User | `AccessError` on pending delete |
| `test_claim_manager_can_unlink` | Claims Manager | Delete succeeds |
| `test_base_user_cannot_write_tx_line` | Internal User | `AccessError` on line write |
| `test_manager_can_write_tx_line` | Transaction Manager | Write succeeds |
| New | Logistics | Write succeeds if the logistics row is kept |
| New | Sales Rep | Line read succeeds. Line write raises `AccessError` |
| New | Internal User uploading `claim_pics` | Document remains. One claim, same transaction and load. A second save does not duplicate. A conflicting association creates no claim. |
| New | Any user | CSV menu is absent and `action_import` raises the retirement error |

Extend `tests/test_legacy_import_ui_retired.py` for this wizard. Update `test_claim_pictures_keep_the_exact_subject` to the gated create.

## Cron corrections, still not applied

Both methods are in `plasticos_claims/tests/test_cron_idempotency.py`. They are independent of the ACL change and were left unchanged because the last instruction before publication was read-only.

Rename `test_scale_tickets_leave_unloaded_transaction` to `test_scale_tickets_leave_transaction_without_loads`:

- Assert `"load_id" not in transaction._fields` and `load_ids` is empty.
- Call `cron_check_scale_tickets` twice.
- Assert historical `scale_ticket_escalated` is still false.

Rename `test_compliance_audit_clears_verified_on_expired_document` to `test_compliance_audit_keeps_historical_verification`:

- Create the expired document without `verified`, `verified_by`, or `verified_at`.
- Assert create or write of `verified=True` raises `AccessError`.
- Verify only through `action_verify` as a documents user, after exact association.
- Call `_cron_compliance_audit` twice.
- Assert `verified`, `verified_by`, and `verified_at` are unchanged.

Direct verification writes are refused in `plasticos_documents/models/document.py` (`_refuse_direct_decision_write`). The legal path is `action_verify`.

## Effective access after the two blankets go, logistics row kept

Odoo allows an operation when any group grants it. A record rule with unlink off does not deny delete.

| Actor | Claim | Pending claim delete | Transaction line |
|---|---|---|---|
| Internal User, Sales Rep, Accounting | Denied | Denied | Read only |
| Logistics | Denied | Denied | Read, write, create. No unlink |
| Claims User | Read, write, create | Denied | Read only, unless they also have a line-write group |
| Claims Manager | Full CRUD | Allowed | Same as their other groups |
| Settings / Transaction Manager | Denied until they are actually Claims Manager | Denied | Full CRUD through the manager row |

Header unlink is unchanged while `access_transaction_all` stays. There is no record rule on `plasticos.transaction.line`. The sales-rep own-record rule is header-only.

## Next window

1. Read this file and the PR. Do not merge.
2. Do not redo the four test edits. They are this branch.
3. Ask the operator the logistics and Settings questions before any ACL edit.
4. The cron test renames can land without those answers. They are a separate small change.
5. Publication of a later branch is `make pr` from a clean feature branch. `make push` is retired.
