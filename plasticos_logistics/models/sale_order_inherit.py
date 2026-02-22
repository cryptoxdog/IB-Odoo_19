from odoo import models


class SaleOrderInherit(models.Model):
    _inherit = "sale.order"

    def action_create_load(self):
        """Open load form with this sale order set as default."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.load",
            "view_mode": "form",
            "target": "current",
            "context": {"default_sale_order_id": self.id},
        }
