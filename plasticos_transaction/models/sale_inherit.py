from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    transaction_id = fields.Many2one("plasticos.transaction")

    def action_confirm(self):
        # MRO Note: If plasticos_automation is installed, its action_confirm() runs first
        # (checking approval), then calls super() which reaches here.
        # This ensures transaction creation only happens if approval passes.
        res = super().action_confirm()

        for rec in self:
            if not rec.transaction_id:
                transaction = self.env["plasticos.transaction"].create(
                    {"name": f"TX-{rec.name}", "sale_order_id": rec.id}
                )
                rec.transaction_id = transaction.id
                transaction.action_activate()

        return res
