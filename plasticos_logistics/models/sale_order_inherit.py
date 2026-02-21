from odoo import models

from ..services.rate_engine import get_recent_lane_rate


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_create_load(self):
        for rec in self:
            load = self.env["plasticos.load"].create(
                {
                    "name": f"LOAD-{rec.name}",
                    "sale_order_id": rec.id,
                    "state": "awaiting_ready",
                }
            )

            lane_key = f"{rec.partner_shipping_id.id}-{rec.partner_invoice_id.id}"

            if rec.carrier_id:
                rate = get_recent_lane_rate(self.env, rec.carrier_id.id, lane_key)
                if rate:
                    load.carrier_id = rec.carrier_id.id
                    load.rate_amount = rate
                    load.rate_auto_reused = True
                    load._transition("rate_confirmed")

            return load
