# Surgical remediation map — historical accounting-document safety

No product code was changed. No test was added to a module. No PR was modified or published. PR #301 and PR #303 were not combined.

| Item | Value |
|---|---|
| #301 source | `cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79` (`wt-premerge-301-head`, porcelain 0) |
| #303 source | `190c497bdea1362cad87e231c713efdcd25240d4` (`wt-premerge-303`, porcelain 0) |
| Fixture | `odoo_test_tpl_ee_c9e8a81f52f23680`, fingerprint `c9e8a81f52f23680595b63d3f5ce3730f95db97195384243ef2fd10b35156c30`, parity ee |
| Enterprise | `/Users/ib-mac/Dropbox/Repo_Dropbox_IB/IB-Odoo_19/odoo-enterprise` |
| Clones | `odoo_test_pr301_prov_10242030` and `odoo_test_pr303_post_10242030`, both dropped. The template database is the only `odoo_test_pr*` / template name still present. |

Logs: `surgical/probe1-output.txt`, `surgical/probe2-output.txt`, `surgical/probe3-setup-output.txt`, `surgical/probe3-fail-output.txt`, `surgical/probe3-retry-output.txt`.

## 1. Document provenance (#301 head)

Worksheet 54839 was realized through `native_document_import` on `plasticos.erp.import`, then rolled back. The same sale order was also invoiced with `sale.order._create_invoices()`, and a manual customer invoice was created with `invoice_origin` set to the sale order name.

The reliable document identity is the `ir.model.data` row written by `plasticos_partner_import/models/erp_import_service.py` `_write_identity_marker` (module `plasticos_transaction`). `_move` in `plasticos_transaction/models/native_document_import.py` creates the `account.move` once, leaves it in draft, and writes that marker.

| Document | Marker | `invoice_origin` | `ref` | Line `is_imported` | `sale_line_ids` | State after import |
|---|---|---|---|---|---|---|
| Sale order | `legacy_erp_so_14263` | worksheet `54839` (this is `sale.order.origin`; the order **name** is `14263`) | — | — | — | `sale`; transaction `54839` is `closed` |
| Customer invoice | `legacy_erp_outinv_54839` | `54839` | `54839` | true | empty | draft |
| Vendor bill | `legacy_erp_ininv_591398` | `54839` | vendor invoice `V-7275` | true | empty | draft |
| `_create_invoices()` invoice | none | sale name `14263` | `14263` | false | linked | draft |
| Manual invoice | none | sale name `14263` | empty | false | empty | draft |

`is_imported` is Odoo core `account.field_account_move_line__is_imported`. It is not a field on `account.move`. `invoice_origin` is not authoritative: on the historical invoice it equals the worksheet, which is `sale.order.origin`, and on the operational invoice it equals `sale.order.name`. A line flag can be copied onto a non-imported line. The marker cannot: it is one `ir.model.data` row per imported move, names `legacy_erp_outinv_<worksheet>`, `legacy_erp_ininv_<payable>`, and `legacy_erp_ledger_<ledger>`.

Observed and not diagnosed: the historical customer invoice kept `invoice_date` `2022-04-01` and an empty payment term, and its `invoice_date_due` was `2026-10-25` (the database session date). The dated bill's due date was the header date `2022-03-20`.

## 2. Where posting starts (#303 head)

One in-memory trace, rolled back. One active rule required both an invoice document and a close document. Existing transaction rules were deactivated for the script only.

`plasticos_transaction/models/transaction.py` `_compute_compliance` calls `plasticos.compliance.service.is_compliant` with no purpose. When that returns true and the stored status was `missing`, it assigns `compliant` and then calls `_auto_post_pending_invoices`. That method posts `customer_invoice_id`, draft `vendor_bill_ids`, and draft `freight_bill_ids` in one `action_post()`.

`account.move.action_post` (`account_move_inherit.py`) runs `is_compliant(..., purpose="invoice")` only when `invoice_origin` equals a `sale.order.name` that has `transaction_id`. It looks up vendor bills the same way, by sale name or purchase name. It does not use `_find_linked_transactions` for that check.

| Path | Transaction | What the trace recorded | Result |
|---|---|---|---|
| Historical | `54839`, state `closed`, sale name `14263`, origin `54839` | `is_compliant` purpose `null` only. `_auto_post_pending_invoices` ran while the transaction was closed and the in-memory status was already `compliant`. `action_post` received invoice origin `54839` and bill origin `54839`. No `purpose="invoice"` call. | Both moves **posted** |
| Operational | live sale `S00001`, empty origin, invoice origin `S00001`, `is_imported` false, sale line linked | Unscoped `is_compliant` went false then true. Auto-post selected that invoice. `action_post` then called `purpose="invoice"`, which returned true. | Invoice **posted** |

The purpose gate does not protect the historical drafts. Their origin is the worksheet, so the sale-name lookup misses, and `super().action_post()` still runs. Widening that lookup would run `purpose="invoice"` on the already-linked transaction. In the reproduced case the invoice document was present, so the check would pass and the moves would still post.

Unscoped compliance is the trigger. On one transaction, a true unscoped result implies a true `purpose="invoice"` result, because the invoice rules are a subset of the active rules. `required_for_close` can keep the status `missing`. It does not have its own post gate. The operational `purpose="invoice"` check runs inside `action_post`, after auto-post has already selected the move.

## 3. Failure atomicity and retry (#303 head, same clone after the rollback)

Setup committed a draft transaction `ATOMIC-54839`, a dated customer invoice (`2022-04-01`, marker `legacy_erp_outinv_atomic`), and an undated vendor bill (marker `legacy_erp_ininv_atomic`). One active rule. Compliance was `missing`. Both moves were draft.

The next shell created a verified document and did not catch the error. Posting raised:

`UserError: The Bill/Refund date is required to validate this document.`

Stack: `plasticos.document.create` → `_compute_compliance` → `_auto_post_pending_invoices` → `account.move.action_post` → `account.move._post`.

A new `psql` connection then read:

| Row | Persisted state |
|---|---|
| Transaction `ATOMIC-54839` | `draft`, `compliance_status` **missing** |
| Customer invoice | **draft**, date `2022-04-01` |
| Vendor bill | **draft**, `invoice_date` null |
| `plasticos.document` for that transaction | no row |
| Both xmlid markers | still present |

The in-memory assignment of `compliant` happens before `action_post`. It does not survive a request that lets the `UserError` abort the cursor. The earlier combined-tree probe caught that error in the same cursor and read `compliant` there. That read was not persisted state.

The retry shell then wrote the bill date `2022-03-15` and due date `2022-03-20` and created the document again. Before that write the database still showed `missing`, both drafts, and zero documents. After the commit, `psql` showed `compliant`, both moves **posted**, and one verified document. The workflow retries when the failed request did not commit.

## 4. Correction boundary

**Owner:** `plasticos_transaction/models/transaction.py`, method `_auto_post_pending_invoices`, called from `_compute_compliance` only when `old_status == "missing"`.

**Reproduced failure:** a closed historical transaction whose drafts carry `plasticos_transaction.legacy_erp_outinv_*` and `legacy_erp_ininv_*` goes from `missing` to `compliant` and both drafts post. Cause: auto-post selects every linked draft, and `action_post` does not see a sale order whose name is the worksheet number.

**Smallest correction:** before `action_post`, drop moves that have an `ir.model.data` row in module `plasticos_transaction` whose name starts with `legacy_erp_outinv_`, `legacy_erp_ininv_`, or `legacy_erp_ledger_`. If none remain, do not call `action_post`. Leave the compliance assignment as it is. Historical drafts stay draft through the compliance transition, including an undated bill, and a later document write does not post them because the status is no longer `missing`. An accountant posts them with the ordinary Post button, which still enforces the core bill-date check.

**Alternative — skip when `state == "closed"`.** This covers the status-I worksheet that probe 2 posted. It misses a historical draft linked to a transaction that is not closed. Probe 3 posted the same shaped documents on a draft transaction. It also suppresses auto-post for every closed transaction, including an operational one whose compliance later flips.

**Not the correction:** teaching `action_post` to resolve the transaction through `_find_linked_transactions` or through `sale.order.origin`. That adds the purpose check. It does not keep the drafts unposted once the invoice document exists.

## 5. Behaviors that stay

- An operational invoice from `sale.order._create_invoices()` has `invoice_origin` equal to the sale name, no legacy marker, `is_imported` false, and a linked sale line. The `missing` → `compliant` transition still posts it when the invoice rules pass.
- A direct Post on that operational invoice still calls `purpose="invoice"` and still raises `Missing required documents for invoice posting.` when those documents are absent. `required_for_close` still does not block that post.
- An operational undated bill that is still in the auto-post set still raises `The Bill/Refund date is required to validate this document.` A request that does not catch it still leaves compliance `missing`, both moves draft, and the document unpersisted. Filling the date and creating the document again still posts both.
- #301 still creates historical moves in draft, still writes the three marker prefixes, and still applies the due-date and trade-date rules already tested.
- Closed-transaction cancel and unlink still raise their existing `UserError`s.
- The ACL rows are unchanged by this correction.

## 6. Regression assertions, after approval

Do not add these until the correction is approved.

1. A closed transaction whose customer invoice and vendor bill carry `legacy_erp_outinv_` and `legacy_erp_ininv_` stays draft on `missing` → `compliant`, whether or not the bill has `invoice_date`. Compliance becomes `compliant`. A second document write does not post them.
2. An operational invoice (`invoice_origin` is the sale name, no legacy marker, `is_imported` false, sale line linked) posts on that same transition when the invoice rule is satisfied, and a direct `action_post` raises `Missing required documents for invoice posting.` when it is not.
3. An operational dated invoice plus an operational undated bill, with no legacy markers: document create raises the bill-date `UserError`; a new database connection shows compliance `missing`, both draft, and no document. After `invoice_date` is set, creating the document posts both and stores `compliant`.

## 7. Operator decisions

1. Approve the marker exclusion above, or the closed-state alternative. The marker exclusion is the boundary the probes support.
2. Decide whether a later manual Post of a historical draft should also require `purpose="invoice"` via the transaction already linked on `customer_invoice_id` / `vendor_bill_ids`. Today it does not. Leaving that path alone keeps historical posting as an explicit accounting action and keeps the core date check.
3. The second PR to merge must still bump `plasticos_transaction` above `19.0.2.3.40`. This probe did not change that. Without the bump, Odoo.sh will not load the second PR's transaction Python, including this exclusion if it lands in the second merge.
4. The customer-invoice due date of `2026-10-25` with an empty payment term is outside this correction. Say if it should be diagnosed separately.

## 8. ACL unlink pass — read-only, not executed

`TestTransactionACL.test_base_user_cannot_unlink` (`plasticos_commission/tests/test_security_acl.py`) creates a fresh transaction and expects `AccessError` from `with_user(base_user).unlink()`. The published Community note says the test was not in the failure list. No traceback was published. This campaign did not run the test.

On `190c497`, that source cannot raise `AccessError` for this user and this record:

- `ir.model.access.csv` line 2 grants `base.group_user` read only. Line 10, `access_transaction_all`, grants the same group create, write, and unlink. Odoo 19 `ir.model.access._get_allowed_models` (`ir_model.py`) selects the model when any active row for the user's groups has `perm_unlink`. The union allows unlink, so `check()` does not raise.
- The test user is created with only `base.group_user`. Sales-rep, logistics, and accounting groups imply that group; the implication does not run the other way (`plasticos_security_base/security/security_groups.xml`).
- `rule_transaction_sales_rep` applies only to `group_sales_rep`. `rule_plasticos_close_restrict` applies only to `group_plasticos_manager` and its domain is `(1, '=', 1)`. Neither rule is in force for this user. No other `ir.rule` targets `plasticos.transaction`.
- `transaction.unlink` raises `UserError`, and only when the transaction has a linked invoice or bill or is closed. The test record has neither. `mail.thread.unlink` deletes messages, followers, and scheduled messages with `sudo()`.

The Community pass is **NOT_PROVEN**. Absence from a failure list is not a captured `AccessError`. The two record-rule files that were candidates do not produce it. Claim and transaction-line ACL failures stay out of this campaign.
