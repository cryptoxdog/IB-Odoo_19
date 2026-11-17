import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    pickup_dock_rule = fields.Selection(
        [
            ("fcfs", "First Come First Served"),
            ("appointment", "Appointment Required"),
        ],
        string="Pickup Dock Rule",
        compute="_compute_pickup_dock_rule_from_transaction",
        store=True,
        help="Pickup dock rule from the linked transaction. The purchase order has no delivery-side rule.",
    )

    @api.depends("origin")
    def _compute_pickup_dock_rule_from_transaction(self):
        """Copy the pickup dock rule from the transaction that contains this order.

        Transactions are linked via purchase_order_ids Many2many, so this is a
        reverse lookup. search() order is id, which is what limit=1 selected
        when several transactions contain one purchase order. The first match wins.
        """
        po_tx = {}
        if self.ids:
            transactions = self.env["plasticos.transaction"].search([("purchase_order_ids", "in", list(self.ids))])
            order_ids = set(self.ids)
            for tx in transactions:
                for po in tx.purchase_order_ids:
                    if po.id in order_ids:
                        po_tx.setdefault(po.id, tx)
        for order in self:
            tx = po_tx.get(order.id)
            order.pickup_dock_rule = tx.pickup_dock_rule if tx else False

    def _origin_sale_orders(self):
        """Sale orders named by each purchase order's origin, per ``(company id, name)``."""
        sales_by_key = {}
        origins = list({order.origin for order in self if order.origin})
        if not origins:
            return sales_by_key
        sale_orders = self.env["sale.order"].search(
            [("name", "in", origins), ("company_id", "in", self.company_id.ids)]
        )
        for sale in sale_orders:
            sales_by_key.setdefault((sale.company_id.id, sale.name), []).append(sale)
        return sales_by_key

    def button_confirm(self):
        """Confirm, then attach each order to the transaction of the sale order its origin names.

        The sale order is looked up in the purchase order's company. An origin
        that names more than one sale order is refused before confirmation.
        """
        sales_by_key = self._origin_sale_orders()
        for rec in self:
            if len(sales_by_key.get((rec.company_id.id, rec.origin), [])) > 1:
                raise UserError(
                    f"Cannot confirm {rec.display_name}: more than one sale order is named {rec.origin}. "
                    "Correct the origin so it names exactly one sale order."
                )

        res = super().button_confirm()

        for rec in self:
            sale_orders = sales_by_key.get((rec.company_id.id, rec.origin), [])
            if sale_orders and sale_orders[0].transaction_id:
                sale_orders[0].transaction_id.purchase_order_ids = [(4, rec.id)]

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
        """The one transaction this purchase order belongs to, or nothing when that is not unique."""
        Transaction = self.env["plasticos.transaction"]
        if order.origin:
            sale_orders = self.env["sale.order"].search(
                [("name", "=", order.origin), ("company_id", "=", order.company_id.id)]
            )
            if len(sale_orders) > 1:
                _logger.warning("PO %s: origin %s names more than one sale order", order.name, order.origin)
                return Transaction
            if sale_orders.transaction_id:
                return sale_orders.transaction_id
        holders = Transaction.search([("purchase_order_ids", "in", [order.id])])
        if len(holders) > 1:
            _logger.warning("PO %s belongs to more than one transaction", order.name)
            return Transaction
        return holders
