import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    delivery_term = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Delivery Term",
        compute="_compute_delivery_term_from_transaction",
        store=True,
        help="Delivery term from linked transaction.",
    )

    @api.depends("origin")
    def _compute_delivery_term_from_transaction(self):
        """Compute delivery term from linked transaction.

        Transactions are linked via purchase_order_ids Many2many, so we do
        a reverse lookup to find the transaction that contains this PO.
        """
        po_tx = {}
        if self.ids:
            # Membership stays purchase_order_ids. search() order is id, which
            # is what limit=1 selected when several transactions contain one PO.
            transactions = self.env["plasticos.transaction"].search([("purchase_order_ids", "in", list(self.ids))])
            order_ids = set(self.ids)
            for tx in transactions:
                for po in tx.purchase_order_ids:
                    if po.id in order_ids:
                        po_tx.setdefault(po.id, tx)
        for order in self:
            tx = po_tx.get(order.id)
            order.delivery_term = tx.delivery_term if tx else False

    def button_confirm(self):
        res = super().button_confirm()

        # Batch query: find all SOs by origin in one query
        origins = [rec.origin for rec in self if rec.origin]
        if origins:
            sale_orders = self.env["sale.order"].search([("name", "in", origins)])
            so_by_name = {so.name: so for so in sale_orders}
            for rec in self:
                if rec.origin and rec.origin in so_by_name:
                    so = so_by_name[rec.origin]
                    if so.transaction_id:
                        so.transaction_id.purchase_order_ids = [(4, rec.id)]

        return res

    def button_approve(self, force=False):
        """Override to link created pickings to transaction after native creation.

        Native purchase_stock._create_picking() runs in super().button_approve().
        After that completes, we link the created pickings to the transaction.
        """
        res = super().button_approve(force=force)

        for order in self:
            if not order.picking_ids:
                continue

            tx = self._find_transaction_for_po(order)
            if tx and not tx.delivery_order_id:
                outgoing = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == "outgoing" and p.state != "cancel"
                )
                if outgoing:
                    tx.delivery_order_id = outgoing[0].id
                    _logger.info(
                        "Linked DO %s to TX %s from PO %s",
                        outgoing[0].name,
                        tx.name,
                        order.name,
                    )

        return res

    def _find_transaction_for_po(self, order):
        """Find the transaction linked to this purchase order."""
        tx = None
        if order.origin:
            so = self.env["sale.order"].search([("name", "=", order.origin)], limit=1)
            if so and hasattr(so, "transaction_id") and so.transaction_id:
                tx = so.transaction_id

        if not tx:
            tx = self.env["plasticos.transaction"].search(
                [("purchase_order_ids", "in", [order.id])],
                limit=1,
            )

        return tx
