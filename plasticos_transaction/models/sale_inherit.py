from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one("plasticos.transaction")

    def action_confirm(self):
        res = super().action_confirm()

        for rec in self:
            if not rec.transaction_id:
                transaction = self.env["plasticos.transaction"].create(
                    {"name": f"TX-{rec.name}", "sale_order_id": rec.id}
                )
                rec.transaction_id = transaction.id
                transaction.action_activate()

        return res
