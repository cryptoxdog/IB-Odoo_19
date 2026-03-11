from odoo import models
from odoo.exceptions import UserError

PLASTICOS_TRANSACTION = "plasticos.transaction"


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
        return self.env[PLASTICOS_TRANSACTION].search(
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
        so_by_name, po_by_name = self._batch_fetch_orders()
        self._pre_check_compliance_and_refunds(service, so_by_name)

        res = super().action_post()

        tx_by_po = self._build_tx_by_po(po_by_name)
        self._link_moves_after_post(so_by_name, po_by_name, tx_by_po)

        return res

    def _batch_fetch_orders(self):
        """Batch-fetch sale and purchase orders referenced by invoice origins."""
        out_invoice_origins = [
            rec.invoice_origin for rec in self if rec.move_type == "out_invoice" and rec.invoice_origin
        ]
        in_invoice_origins = [
            rec.invoice_origin for rec in self if rec.move_type == "in_invoice" and rec.invoice_origin
        ]
        all_origins = list(set(out_invoice_origins + in_invoice_origins))

        so_by_name = {}
        po_by_name = {}
        if all_origins:
            sale_orders = self.env["sale.order"].search([("name", "in", all_origins)])
            so_by_name = {so.name: so for so in sale_orders}
            missing_origins = [o for o in in_invoice_origins if o not in so_by_name]
            if missing_origins:
                purchase_orders = self.env["purchase.order"].search([("name", "in", missing_origins)])
                po_by_name = {po.name: po for po in purchase_orders}

        return so_by_name, po_by_name

    def _pre_check_compliance_and_refunds(self, service, so_by_name):
        """Enforce compliance and block refunds against closed transactions before posting."""
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    if service and not service.is_compliant(PLASTICOS_TRANSACTION, so.transaction_id.id):
                        raise UserError("Missing required documents for invoice posting.")

            if rec.move_type in ("out_refund", "in_refund") and rec.reversed_entry_id:
                tx = self._find_linked_transactions(rec.reversed_entry_id.id)
                if tx.filtered(lambda t: t.state == "closed"):
                    raise UserError("Cannot post credit note for closed transaction.")

    def _build_tx_by_po(self, po_by_name):
        """Build a {po_id: transaction} map for the given PO set."""
        po_ids = [po.id for po in po_by_name.values()]
        tx_by_po = {}
        if po_ids:
            transactions = self.env[PLASTICOS_TRANSACTION].search([("purchase_order_ids", "in", po_ids)])
            for tx in transactions:
                for po in tx.purchase_order_ids:
                    tx_by_po[po.id] = tx
        return tx_by_po

    def _link_moves_after_post(self, so_by_name, po_by_name, tx_by_po):
        """Link posted moves to their transactions via SO or PO origin."""
        for rec in self:
            if rec.move_type == "out_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    so.transaction_id.customer_invoice_id = rec.id

            if rec.move_type == "in_invoice" and rec.invoice_origin:
                so = so_by_name.get(rec.invoice_origin)
                if so and so.transaction_id:
                    so.transaction_id.vendor_bill_ids = [(4, rec.id)]
                else:
                    po = po_by_name.get(rec.invoice_origin)
                    if po and po.id in tx_by_po:
                        tx_by_po[po.id].vendor_bill_ids = [(4, rec.id)]

    def unlink(self):
        for move in self:
            tx = self._find_linked_transactions(move.id)
            if tx.filtered(lambda t: t.state == "closed"):
                raise UserError("Cannot delete invoice/bill linked to closed transaction.")
        return super().unlink()
