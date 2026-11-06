---
auto_generated: false
authority: derived-index
component_id: plasticos_transaction
component_name: Plasticos Transaction Spine
module_version: 19.0.2.3.58
layer: 5
installable: true
auto_install: true
application: true
depends:
  - plasticos_base
  - base
  - mail
  - product
  - account
  - account_debit_note
  - sale_management
  - sale_crm
  - purchase
  - purchase_stock
  - stock
  - plasticos_material_profile
  - plasticos_facility_profile
  - plasticos_intake
  - plasticos_product
  - plasticos_offer
  - plasticos_partner_import
models_owned:
  - plasticos.transaction
  - plasticos.transaction.line
  - plasticos.audit.cron
  - plasticos.transaction.import.service
  - plasticos.transaction.reopen.wizard
  - plasticos.transaction.import.wizard
  - plasticos.tx.bulk.wizard
  - plasticos.transaction.bulk.assign.wizard
models_extended:
  - plasticos.transaction
  - sale.order
  - purchase.order
  - account.move
  - account.move.line
  - plasticos.offer
  - plasticos.intake
  - plasticos.erp.import
  - res.users
  - res.partner
crons:
  - cron_plasticos_monthly_audit
---

# Plasticos Transaction Spine

The front matter above is a derived index. `__manifest__.py` and the `_name` / `_inherit` lines in `models/` and `wizards/` win on any conflict.

## What it does

One `plasticos.transaction` per brokered deal: the supplier, the buyer, the sale and purchase orders, the invoices and bills, freight, and the margin. Confirming a sale order is what creates the transaction.

## How it works

- **Compile on confirm.** `sale.order.action_confirm()` (`models/sale_inherit.py`) creates a transaction for each confirmed order that has no `transaction_id`.
  - **Live sale.** The transaction is named from the worksheet number on `origin`, or from the `SM-` sequence when `origin` is empty. It is activated (`draft` → `active`), and an accepted offer named in `origin` is linked back to it.
  - **Historical import (`import_mode`).** `_compile_worksheet_transactions()` creates one transaction per worksheet number on `origin`, named with that number, starting `closed`. The source order date is kept: `date_order` is not reset on confirmation. Calling it again creates nothing new.
- **Draft order for an accepted offer.** `sale.order._plasticos_draft_order_for_offer()` creates or reuses one draft sale order for an offer accepted on a native CRM Opportunity (`sale.order.opportunity_id` from `sale_crm`). It confirms, posts, and mails nothing.
- **ERP historical documents.** `models/legacy_erp_import_service.py` overrides `plasticos.erp.import._extend_historical_import()` from `plasticos_partner_import`. It writes `sale.order`, `purchase.order`, and draft `account.move` records through `models/native_document_import.py`, and does not create `plasticos.transaction` itself; the import confirms the sale orders, and that confirmation compiles the transactions. It creates no payment and posts nothing. A purchase order's `date_approve` is set to the earliest trade date (`GPLedger.TradeDt`) of the worksheets it serves; `date_order` stays the source PO or order date. There is no `transaction_date` field.
- **States** of `plasticos.transaction`: `draft`, `active`, `pending_supplier`, `supplier_not_ready`, `supplier_ready`, `do_created`, `dispatched`, `in_progress`, `in_transit`, `delivered`, `invoiced`, `closed`, `cancelled`. Commands include `action_activate`, `action_mark_supplier_ready`, `action_mark_supplier_not_ready`, `action_mark_do_created`, `action_mark_dispatched`, `action_mark_in_transit`, `action_mark_delivered`, and `action_close`.
- **Close.** `action_close` requires the manager group, a posted customer invoice and vendor bills, no missing documents, logistics not behind, and `gross_margin >= 0`, then closes under an advisory lock. `action_reopen_historical` reopens one closed imported transaction to `active` with a reason (`plasticos.transaction.reopen.wizard`).
- **Margin.** `_compute_financials`:
  - revenue is the customer invoice plus its debit notes and its reversals (refunds count negative);
  - purchase cost is the vendor bills;
  - freight is the signed total of `freight_bill_ids`, or `freight_actual` when those bills total zero;
  - `gross_margin` = revenue − (purchase cost + freight + other expenses) + freight chargebacks + lightweight penalties.
    Chargebacks and penalties come from `plasticos_claims` and are zero without it.
- **Commission.** `commission_amount` is a stub here and stays zero unless `plasticos_commission` overrides `_compute_commission`. `net_margin` = `gross_margin` − `commission_amount`. There is no `commission_id` field.
- **Monthly audit.** `plasticos.audit.cron.run_monthly_audit()` lists closed transactions with a negative gross margin, and, when `plasticos_commission` adds `commission_locked`, closed ones whose commission is not locked.
- **Other extensions.** `transaction_bridge.py` adds `intake_id` to `plasticos.transaction`. `plasticos.offer`, `plasticos.intake`, and `res.partner` get transaction links and counts. `res.users` gets `default_commission_rate`. The `account.move` extension links a posted customer invoice to its sale order's transaction (refusing when that transaction is missing documents), refuses to cancel a move linked to a closed transaction, and protects imported historical originals. The `account.move.line` extension protects the lines of those originals.
- **Bulk edits.** `plasticos.tx.bulk.wizard` and `plasticos.transaction.bulk.assign.wizard` update or assign many transactions.
- **Install hook.** `post_init_hook` in `hooks.py` grants this module's groups to the users of the crons it owns.

The CSV wizard (`plasticos.transaction.import.wizard`) and `plasticos.transaction.import.service` are the legacy WksDetail CSV import. The ERP import above is the current path.

## Models

| Model                                      | Kind               | File                                        |
| ------------------------------------------ | ------------------ | ------------------------------------------- |
| `plasticos.transaction`                    | owned              | `models/transaction.py`                     |
| `plasticos.transaction.line`               | owned              | `models/transaction_line.py`                |
| `plasticos.audit.cron`                     | owned              | `models/audit_cron.py`                      |
| `plasticos.transaction.import.service`     | owned, abstract    | `models/transaction_import_service.py`      |
| `plasticos.transaction.reopen.wizard`      | owned, transient   | `wizards/transaction_reopen_wizard.py`      |
| `plasticos.transaction.import.wizard`      | owned, transient   | `wizards/transaction_import_wizard.py`      |
| `plasticos.tx.bulk.wizard`                 | owned, transient   | `wizards/transaction_bulk_update_wizard.py` |
| `plasticos.transaction.bulk.assign.wizard` | owned, transient   | `wizards/transaction_bulk_assign_wizard.py` |
| `plasticos.transaction`                    | extended           | `models/transaction_bridge.py`              |
| `sale.order`                               | extended           | `models/sale_inherit.py`                    |
| `purchase.order`                           | extended           | `models/purchase_inherit.py`                |
| `account.move`                             | extended           | `models/account_move_inherit.py`            |
| `account.move.line`                        | extended           | `models/account_move_inherit.py`            |
| `plasticos.offer`                          | extended           | `models/offer_bridge.py`                    |
| `plasticos.intake`                         | extended           | `models/intake_bridge.py`                   |
| `plasticos.erp.import`                     | extended, abstract | `models/legacy_erp_import_service.py`       |
| `res.users`                                | extended           | `models/res_users_inherit.py`               |
| `res.partner`                              | extended           | `models/partner_bridge.py`                  |

## Runtime

- The only cron in this module is `cron_plasticos_monthly_audit` in `data/audit_cron.xml`: monthly, `run_monthly_audit()`, as `plasticos_base.user_system_cron`. The XML sets no `active` field.
- `plasticos_logistics` declares two crons that call `_cron_supplier_confirmation_followup` and `_cron_auto_create_delivery_orders` on this model. The midnight recompute belongs to `plasticos_base`.
- The transaction sequence is `SM-<year>-` (`data/sequence.xml`).
- `installable`, `application`, and `auto_install` are true.

## Boundaries

- The importer creates no transaction directly; sale-order confirmation does.
- No payment, clearing entry, or posting is created by the historical import.
- Commission rules and payouts belong to `plasticos_commission`.

## Read next

- [`models/sale_inherit.py`](models/sale_inherit.py)
- [`models/transaction.py`](models/transaction.py)
- [`models/native_document_import.py`](models/native_document_import.py)
- [`../plasticos_partner_import/README.md`](../plasticos_partner_import/README.md)
- [ADR-021](../docs/adr/ADR-021-erp-sql-crm-api-import.md)
