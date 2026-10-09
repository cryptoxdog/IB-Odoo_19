from datetime import date

from odoo import Command, fields, models

COMMISSION_SETTLED_BEFORE = date(2026, 6, 1)

PLASTICOS_TRANSACTION = "plasticos.transaction"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one(PLASTICOS_TRANSACTION, ondelete="restrict")

    def action_confirm(self):
        """Confirm the sale order and compile one transaction from its documents.

        A historical import (``import_mode``) names the transaction with the
        worksheet number. An invoiced worksheet is created closed. A worksheet
        still marked WORK stays active. A live sale with no worksheet origin
        keeps the sequence name and is activated.
        """
        res = super().action_confirm()
        recs_needing_tx = self.filtered(lambda order: not order.transaction_id)
        if not recs_needing_tx:
            return res
        historical = bool(self.env.context.get("import_mode"))
        transactions = self.env[PLASTICOS_TRANSACTION]
        for order in recs_needing_tx:
            tx = transactions.with_context(import_mode=historical).create(order._transaction_vals(historical))
            order.transaction_id = tx.id
            order._post_worksheet_note(tx, historical)
            if tx.state == "draft":
                tx.action_activate()
        return res

    def _transaction_vals(self, historical: bool) -> dict:
        """Values the transaction compiler can read off this sale order."""
        self.ensure_one()
        worksheet = (self.origin or "").strip()
        vals = {
            "sale_order_id": self.id,
            "buyer_id": self.partner_id.id,
            "user_id": self._salesperson_id(),
            "product_id": self.order_line[:1].product_id.id,
        }
        if worksheet:
            assigned = (self.env.context.get("erp_salesperson_by_origin") or {}).get(worksheet)
            if assigned:
                vals["user_id"] = assigned
            carrier = (self.env.context.get("erp_carrier_by_origin") or {}).get(worksheet)
            if carrier:
                vals["carrier_id"] = carrier
            vals.update(self._worksheet_document_vals(worksheet))
        if historical:
            outcome = (self.env.context.get("erp_state_by_origin") or {}).get(worksheet) or "closed"
            if outcome == "closed":
                vals["state"] = "closed"
            elif outcome == "cancelled":
                vals["state"] = "cancelled"
            if vals.get("name") == worksheet:
                freight = (self.env.context.get("erp_freight_by_origin") or {}).get(worksheet) or 0.0
                other = (self.env.context.get("erp_other_by_origin") or {}).get(worksheet) or 0.0
                if freight:
                    vals["freight_actual"] = freight
                if other:
                    vals["other_expenses"] = other
                self._lock_historical_commission(vals, worksheet)
        return vals

    def _lock_historical_commission(self, vals: dict, worksheet: str) -> None:
        """Stored worksheet commission. Deals before the cutoff are already settled."""
        if "commission_locked" not in self.env[PLASTICOS_TRANSACTION]._fields:
            return
        amount = (self.env.context.get("erp_commission_by_origin") or {}).get(worksheet) or 0.0
        vals["commission_locked"] = True
        vals["commission_locked_amount"] = amount
        order_day = self.date_order.date() if self.date_order else None
        vals["commission_payout_state"] = "paid" if order_day and order_day < COMMISSION_SETTLED_BEFORE else "unpaid"

    def _post_worksheet_note(self, transaction, historical: bool) -> None:
        """Sticky note and speech bubble belong on the transaction log, not the sale order."""
        if not historical:
            return
        worksheet = (self.origin or "").strip()
        note = (self.env.context.get("erp_note_by_origin") or {}).get(worksheet)
        if note:
            transaction.message_post(body=note, message_type="comment", subtype_xmlid="mail.mt_note")

    def _salesperson_id(self) -> int | bool:
        """Partner salesperson. The import user is not a salesperson."""
        self.ensure_one()
        user = self.user_id
        bot = self.env.ref("base.user_root", raise_if_not_found=False)
        if not user or user == bot:
            return False
        return user.id

    def _worksheet_document_vals(self, worksheet: str) -> dict:
        """Purchase order, supplier, and draft invoices that share this worksheet number."""
        vals = {"name": self._worksheet_transaction_name(worksheet)}
        purchases = self.env["purchase.order"].search([("origin", "=", worksheet)])
        if purchases:
            vals["purchase_order_ids"] = [Command.set(purchases.ids)]
            supplier = purchases.filtered("partner_id")[:1].partner_id
            if supplier:
                vals["supplier_id"] = supplier.id
        moves = self.env["account.move"].search(
            [
                ("invoice_origin", "=", worksheet),
                ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
                ("state", "!=", "cancel"),
            ]
        )
        invoice = moves.filtered(lambda move: move.move_type in ("out_invoice", "out_refund"))[:1]
        if invoice and not self.env[PLASTICOS_TRANSACTION].search([("customer_invoice_id", "=", invoice.id)], limit=1):
            vals["customer_invoice_id"] = invoice.id
        bills = moves.filtered(lambda move: move.move_type in ("in_invoice", "in_refund"))
        if bills:
            vals["vendor_bill_ids"] = [Command.set(bills.ids)]
        return vals

    def _worksheet_transaction_name(self, worksheet: str) -> str:
        """Worksheet number, or worksheet plus sale number when that name is taken."""
        taken = self.env[PLASTICOS_TRANSACTION].search([("name", "=", worksheet)], limit=1)
        if not taken:
            return worksheet
        return f"{worksheet}-{self.name}"
