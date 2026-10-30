# GMP-129 — load membership and milestone follow-up

**Task:** Repair open transaction sale-order reassignment while loads are linked, and new load attachment racing a milestone.
**Tier:** RUNTIME
**Branch:** `fix/load-membership-milestone-integrity`
**Code commit:** `fc63e5db`
**Base:** Staging `42556d2e` (merge of PR #342). Owner seams `plasticos_transaction/models/transaction.py` and `plasticos_logistics/models/load.py` are unchanged since inspected `2dc516aa`.
**Worktree:** isolated from the dirty Staging checkout. The merged multi-load branch was not reopened.

## What changed

- An open transaction with linked loads cannot move to a different sale order. A transaction with no loads still can. Closed-transaction immutability still runs first.
- Dispatch, in-transit, delivery, and close take the load lock order: sale order, then transaction, then linked loads.
- Creating, reparenting, or deleting a load bumps `plasticos_transaction.write_date`. The primary key is not updated. Under PostgreSQL repeatable read, a milestone cursor that already read the parent then fails serialization or, on the request retry, sees the new load and refuses to advance.
- Versions: `plasticos_transaction` `19.0.2.3.45`, `plasticos_logistics` `19.0.1.14.10`. No migration, column, ACL, or accounting change.

## Tests

Enterprise fixture `odoo_test_tpl_ee_c9e8a81f52f23680`, clone `odoo_test_wb871ad0d10`.

| Run | Result |
|---|---|
| `make test-module m=plasticos_logistics fresh=0` | 152 tests, 0 failed, 0 errors |
| `make test-odoo fresh=0` | 1103 tests, 8 failed, 2 errors |

The logistics run includes sale-order reassignment, direct parent create, both dispatch races, the stale-snapshot race, delayed auto-link, reparent, unlink, zero-load, and two-load acceptance.

The original seven failures are still failures:

- `TestTransactionClaimsBridgeDepends.test_freight_chargeback_recovery_flows_to_transaction`
- `TestTransactionClaimsBridgeDepends.test_lightweight_penalty_recovery_flows_to_transaction`
- `TestOfferBridge.test_offer_accept_creates_transaction`
- `TestOfferActions.test_action_accept_creates_transaction`
- `TestTransactionACL.test_base_user_cannot_write_tx_line`
- `TestClaimACL.test_claim_user_cannot_unlink`
- `TestClaimACL.test_no_group_cannot_read`

Three more results are outside this diff. They are not a second clean-tree baseline run:

- `TestCronInDomain.test_compliance_audit_clears_verified_on_expired_document` — `AccessError: Business verification cannot be written directly.`
- `TestCronInDomain.test_scale_tickets_leave_unloaded_transaction` — `AttributeError` on removed `load_id`
- `TestWebLeadOpportunity.test_hot_admission_creates_one_new_opportunity_without_partner` — `review_status` is `clarification_required`

## Files

- `plasticos_transaction/models/transaction.py`
- `plasticos_transaction/__manifest__.py`
- `plasticos_logistics/models/load.py`
- `plasticos_logistics/__manifest__.py`
- `plasticos_logistics/tests/test_load_cardinality.py`
