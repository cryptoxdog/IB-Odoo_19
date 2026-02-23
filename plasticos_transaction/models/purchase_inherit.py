from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        res = super().button_confirm()

        for rec in self:
            if rec.origin:
                so = self.env["sale.order"].search([("name", "=", rec.origin)], limit=1)
                if so and so.transaction_id:
                    so.transaction_id.purchase_order_ids = [(4, rec.id)]

        return res
