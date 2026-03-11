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
        service = self.env["plasticos.compliance.service"] if "plasticos.compliance.service" in self.env else None

        # Batch query: collect all invoice_origins for SO lookup
        out_invoice_origins = [
            rec.invoice_origin for rec in self if rec.move_type == "out_invoice" and rec.invoice_origin
        ]
        in_invoice_origins = [
            rec.invoice_origin for rec in self if rec.move_type == "in_invoice" and rec.invoice_origin
        ]
        all_origins = list(set(out_invoice_origins + in_invoice_origins))

        # Batch fetch SOs and POs
        so_by_name = {}
        po_by_name = {}
        if all_origins:
            sale_orders = self.env["sale.order"].search([("name", "in", all_origins)])
            so_by_name = {so.name: so for so in sale_orders}
            # For origins not found as SOs, try POs
            missing_origins = [o for o in in_invoice_origins if o not in so_by_name]
            if missing_origins:
                purchase_orders = self.env["purchase.order"].search([("name", "in", missing_origins)])
                po_by_name = {po.name: po for po in purchase_orders}

        # Pre-check compliance BEFORE posting (prevents side effects on rollback)
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
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

        # Batch fetch transactions for POs (for vendor bill linking)
        po_ids = [po.id for po in po_by_name.values()]
        tx_by_po = {}
        if po_ids:
            transactions = self.env["plasticos.transaction"].search([("purchase_order_ids", "in", po_ids)])
            for tx in transactions:
                for po in tx.purchase_order_ids:
                    tx_by_po[po.id] = tx

        # Link moves to transactions AFTER successful post
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    so.transaction_id.customer_invoice_id = rec.id

            if rec.move_type == "in_invoice" and rec.invoice_origin:
                # Try linking via Sale Order (if origin is SO name)
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    so.transaction_id.vendor_bill_ids = [(4, rec.id)]
                else:
                    # Try linking via Purchase Order (if origin is PO name)
                    po = po_by_name.get(rec.invoice_origin)
                    if po and po.id in tx_by_po:
                        tx_by_po[po.id].vendor_bill_ids = [(4, rec.id)]

        return res

    def unlink(self):
        for move in self:
            tx = self._find_linked_transactions(move.id)
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot delete invoice/bill linked to closed transaction.")
        return super().unlink()
