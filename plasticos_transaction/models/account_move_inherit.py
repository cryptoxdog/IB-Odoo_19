from odoo import models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    # action_post: on posting, link move to transaction (SO -> tx) and enforce compliance
    #   before setting customer_invoice_id. Prevents posting customer invoice if tx missing docs.
    # button_cancel: prevent cancelling a move that is linked to a closed transaction
    #   (audit integrity: closed tx must not have its invoices/bills undone).

    def _find_linked_transactions(self, move_id):
        """Find transactions linked to a move via any bill type.

        Checks customer_invoice_id, vendor_bill_ids, AND freight_bill_ids.
        """
        return self.env["plasticos.transaction"].search(
            [
                "|",
                "|",
                ("customer_invoice_id", "=", move_id),
                ("vendor_bill_ids", "in", move_id),
                ("freight_bill_ids", "in", move_id),
            ]
        )

    def button_cancel(self):
        for move in self:
            tx = self._find_linked_transactions(move.id)
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot cancel invoice/bill linked to closed transaction.")
        return super().button_cancel()

    def action_post(self):
        """Post invoice/bill with compliance check BEFORE posting.

        Compliance check runs before super().action_post() to prevent side effects
        (webhooks, email notifications) from firing before potential rollback.
        """
        service = self.env.get("plasticos.compliance.service")

        # Pre-check compliance BEFORE posting (prevents side effects on rollback)
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = self.env["sale.order"].search([("name", "=", rec.invoice_origin)], limit=1)
                if so and so.transaction_id:
                    if service and not service.is_compliant("plasticos.transaction", so.transaction_id.id):
                        raise UserError("Missing required documents for invoice posting.")

            # Block credit note post when reversed move is linked to closed transaction
            if rec.move_type in ("out_refund", "in_refund") and rec.reversed_entry_id:
                tx = self._find_linked_transactions(rec.reversed_entry_id.id)
                if tx.filtered(lambda t: t.state == "closed"):
                    raise UserError("Cannot post credit note for closed transaction.")

        # Now safe to post
        res = super().action_post()

        # Link moves to transactions AFTER successful post
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = self.env["sale.order"].search([("name", "=", rec.invoice_origin)], limit=1)
                if so and so.transaction_id:
                    so.transaction_id.customer_invoice_id = rec.id

            if rec.move_type == "in_invoice" and rec.invoice_origin:
                so = self.env["sale.order"].search([("name", "=", rec.invoice_origin)], limit=1)
                if so and so.transaction_id:
                    so.transaction_id.vendor_bill_ids = [(4, rec.id)]

        return res

    def unlink(self):
        for move in self:
            tx = self._find_linked_transactions(move.id)
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot delete invoice/bill linked to closed transaction.")
        return super().unlink()
