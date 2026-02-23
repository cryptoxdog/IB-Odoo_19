from odoo import models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    # action_post: on posting, link move to transaction (SO -> tx) and enforce compliance
    #   before setting customer_invoice_id. Prevents posting customer invoice if tx missing docs.
    # button_cancel: prevent cancelling a move that is linked to a closed transaction
    #   (audit integrity: closed tx must not have its invoices/bills undone).

    def button_cancel(self):
        for move in self:
            tx = self.env["plasticos.transaction"].search(
                [
                    "|",
                    ("customer_invoice_id", "=", move.id),
                    ("vendor_bill_ids", "in", move.id),
                ]
            )
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot cancel invoice/bill linked to closed transaction.")
        return super().button_cancel()

    def action_post(self):
        service = self.env.get("plasticos.compliance.service")
        res = super().action_post()

        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = self.env["sale.order"].search([("name", "=", rec.invoice_origin)], limit=1)
                if so and so.transaction_id:
                    tx = so.transaction_id

                    if service and not service.is_compliant("plasticos.transaction", tx.id):
                        raise UserError("Missing required documents for invoice posting.")

                    tx.customer_invoice_id = rec.id

            if rec.move_type == "in_invoice" and rec.invoice_origin:
                so = self.env["sale.order"].search([("name", "=", rec.invoice_origin)], limit=1)
                if so and so.transaction_id:
                    so.transaction_id.vendor_bill_ids = [(4, rec.id)]

            # Block credit note post when reversed move is linked to closed transaction
            if rec.move_type in ("out_refund", "in_refund") and rec.reversed_entry_id:
                tx = self.env["plasticos.transaction"].search(
                    [
                        "|",
                        ("customer_invoice_id", "=", rec.reversed_entry_id.id),
                        ("vendor_bill_ids", "in", rec.reversed_entry_id.id),
                    ]
                )
                if tx.filtered(lambda t: t.state == "closed"):
                    raise UserError("Cannot post credit note for closed transaction.")

        return res

    def unlink(self):
        for move in self:
            tx = self.env["plasticos.transaction"].search(
                [
                    "|",
                    ("customer_invoice_id", "=", move.id),
                    ("vendor_bill_ids", "in", move.id),
                ]
            )
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot delete invoice/bill linked to closed transaction.")
        return super().unlink()
