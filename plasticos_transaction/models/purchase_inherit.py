from odoo import api, fields, models


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
        for order in self:
            tx = self.env["plasticos.transaction"].search(
                [("purchase_order_ids", "in", [order.id])],
                limit=1,
            )
            if tx:
                order.delivery_term = tx.delivery_term
            else:
                order.delivery_term = False

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
