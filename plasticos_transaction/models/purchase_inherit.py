from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

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
