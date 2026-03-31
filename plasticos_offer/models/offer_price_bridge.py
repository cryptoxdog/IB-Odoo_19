"""Auto-populate price_per_lb from intake match line typical_price.

Extends plasticos.offer with a compute helper so the offer form
shows the buyer's typical price when created from action_send_offers.
This is a pure additive extension — no existing offer.py code is modified.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PlasticosOfferPriceBridge(models.Model):
    _inherit = "plasticos.offer"

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-fill price_per_lb from match line typical_price when zero/unset."""
        for vals in vals_list:
            intake_id = vals.get("intake_id")
            buyer_id = vals.get("buyer_id")
            price = vals.get("price_per_lb") or 0.0

            if intake_id and buyer_id and price == 0.0:
                match_line = self.env["plasticos.intake.match"].search(
                    [
                        ("intake_id", "=", intake_id),
                        ("buyer_id", "=", buyer_id),
                        ("typical_price", ">", 0.0),
                    ],
                    limit=1,
                    order="typical_price desc",
                )
                if match_line:
                    vals["price_per_lb"] = match_line.typical_price
                    _logger.debug(
                        "offer create: auto-filled price_per_lb=%.4f from match line %s",
                        match_line.typical_price,
                        match_line.id,
                    )
        return super().create(vals_list)
