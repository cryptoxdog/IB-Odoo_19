from datetime import date

from odoo import Command, fields, models

COMMISSION_SETTLED_BEFORE = date(2026, 6, 1)

PLASTICOS_TRANSACTION = "plasticos.transaction"


def _worksheet_numbers(origin: str | None) -> list[str]:
    """Worksheet numbers stored on ``origin``; one native order can serve several worksheets."""
    return [token.strip() for token in (origin or "").split(",") if token.strip()]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one(PLASTICOS_TRANSACTION, ondelete="restrict")

    def _prepare_confirmation_values(self):
        """A historical order (``import_mode``) keeps its source order date on confirmation."""
        values = super()._prepare_confirmation_values()
        if self.env.context.get("import_mode"):
            values.pop("date_order", None)
        return values

    def action_confirm(self):
        """Confirm the sale order and compile its transactions.

        A historical import (``import_mode``) compiles one transaction per
        worksheet number on ``origin``, named with the worksheet number. An
        invoiced worksheet is created closed. A worksheet still marked WORK
        stays active. A live sale with no worksheet origin keeps the sequence
        name and is activated.
        """
        res = super().action_confirm()
        if self.env.context.get("import_mode"):
            self._compile_worksheet_transactions()
            return res
        recs_needing_tx = self.filtered(lambda order: not order.transaction_id)
        if not recs_needing_tx:
            return res
        transactions = self.env[PLASTICOS_TRANSACTION]
        for order in recs_needing_tx:
            worksheet = (order.origin or "").strip()
            tx = transactions.create(order._transaction_vals(False, worksheet))
            order.transaction_id = tx.id
            if tx.state == "draft":
                tx.action_activate()
        return res

    def _compile_worksheet_transactions(self):
        """One transaction per worksheet on each confirmed order. Safe to call again.

        A worksheet whose name is already a transaction is left alone. When one
        worksheet carries several sale orders, the lowest-numbered order
        compiles it and the others are named in its log.
        """
        transactions = self.env[PLASTICOS_TRANSACTION]
        documents = self.env.context.get("erp_documents_by_origin") or {}
        for order in self:
            if order.state != "sale":
                continue
            for worksheet in _worksheet_numbers(order.origin):
                if transactions.search([("name", "=", worksheet)], limit=1):
                    continue
                sales = (documents.get(worksheet) or {}).get("sales") or []
                eligible = self.browse(sales).exists().filtered(lambda sale: sale.state == "sale").ids
                if eligible and order.id != min(eligible):
                    continue
                tx = transactions.with_context(import_mode=True).create(order._transaction_vals(True, worksheet))
                if not order.transaction_id:
                    order.transaction_id = tx.id
                order._post_worksheet_note(tx, worksheet, sales)
                if tx.state == "draft":
                    tx.action_activate()

    def _transaction_vals(self, historical: bool, worksheet: str) -> dict:
        """Values the transaction compiler can read off this sale order for one worksheet."""
        self.ensure_one()
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
        """Stored worksheet commission. Deals ordered before the cutoff are already settled."""
        if "commission_locked" not in self.env[PLASTICOS_TRANSACTION]._fields:
            return
        amount = (self.env.context.get("erp_commission_by_origin") or {}).get(worksheet) or 0.0
        vals["commission_locked"] = True
        vals["commission_locked_amount"] = amount
        order_day = fields.Date.to_date((self.env.context.get("erp_order_day_by_origin") or {}).get(worksheet) or None)
        if order_day is None and self.date_order:
            order_day = self.date_order.date()
        vals["commission_payout_state"] = "paid" if order_day and order_day < COMMISSION_SETTLED_BEFORE else "unpaid"

    def _post_worksheet_note(self, transaction, worksheet: str, sales: list[int]) -> None:
        """Sticky note, speech bubble, second commission recipient, and sibling orders go on the transaction log."""
        parts = []
        note = (self.env.context.get("erp_note_by_origin") or {}).get(worksheet)
        if note:
            parts.append(note)
        slots = (self.env.context.get("erp_commission_slots_by_origin") or {}).get(worksheet) or []
        paid = [slot for slot in slots if slot.get("code") and slot.get("amount")]
        if len({slot["code"] for slot in paid}) > 1:
            parts.append(
                "Commission slots: "
                + "; ".join(f"slot {slot['slot']} {slot['code']} {slot['amount']:.2f}" for slot in paid)
            )
        siblings = self.browse([sale_id for sale_id in sales if sale_id != self.id]).exists()
        if siblings:
            parts.append("Worksheet also carries sale order(s): " + ", ".join(siblings.mapped("name")))
        if parts:
            transaction.message_post(body="\n\n".join(parts), message_type="comment", subtype_xmlid="mail.mt_note")

    def _salesperson_id(self) -> int | bool:
        """Partner salesperson. The import user is not a salesperson."""
        self.ensure_one()
        user = self.user_id
        bot = self.env.ref("base.user_root", raise_if_not_found=False)
        if not user or user == bot:
            return False
        return user.id

    def _worksheet_document_vals(self, worksheet: str) -> dict:
        """Purchase orders, supplier, invoice, and bills that belong to this worksheet.

        The import hands over the documents it realized for the worksheet. A
        live order without that context falls back to documents whose origin
        is exactly the worksheet number.
        """
        vals = {"name": self._worksheet_transaction_name(worksheet)}
        documents = (self.env.context.get("erp_documents_by_origin") or {}).get(worksheet)
        moves = self.env["account.move"]
        if documents is not None:
            purchases = self.env["purchase.order"].browse(documents.get("purchases") or []).exists()
            invoice = moves.browse([documents["invoice"]] if documents.get("invoice") else []).exists()
            bills = moves.browse(documents.get("bills") or []).exists()
            freight_bills = moves.browse(documents.get("freight_bills") or []).exists()
        else:
            purchases = self.env["purchase.order"].search([("origin", "=", worksheet)])
            found = moves.search(
                [
                    ("invoice_origin", "=", worksheet),
                    ("move_type", "in", ("out_invoice", "out_refund", "in_invoice", "in_refund")),
                    ("state", "!=", "cancel"),
                ]
            )
            invoice = found.filtered(lambda move: move.move_type in ("out_invoice", "out_refund"))[:1]
            bills = found.filtered(lambda move: move.move_type in ("in_invoice", "in_refund"))
            freight_bills = moves
        if purchases:
            vals["purchase_order_ids"] = [Command.set(purchases.ids)]
            supplier = purchases.filtered("partner_id")[:1].partner_id
            if supplier:
                vals["supplier_id"] = supplier.id
        if invoice and not self.env[PLASTICOS_TRANSACTION].search([("customer_invoice_id", "=", invoice.id)], limit=1):
            vals["customer_invoice_id"] = invoice.id
        if bills:
            vals["vendor_bill_ids"] = [Command.set(bills.ids)]
        if freight_bills:
            vals["freight_bill_ids"] = [Command.set(freight_bills.ids)]
        return vals

    def _worksheet_transaction_name(self, worksheet: str) -> str:
        """Worksheet number, or worksheet plus sale number when that name is taken."""
        taken = self.env[PLASTICOS_TRANSACTION].search([("name", "=", worksheet)], limit=1)
        if not taken:
            return worksheet
        return f"{worksheet}-{self.name}"
