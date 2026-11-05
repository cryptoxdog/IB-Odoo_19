"""Auto-populate price_per_lb from intake match line typical_price (legacy intake offers only).

Extends plasticos.offer with a create helper so a manually entered intake
offer shows the buyer's typical price. An offer created from a reviewed Gate
match result (``match_result_id`` set, owned by plasticos_crm_bridge) carries
no price authority from the match: its terms are the broker's and are left
untouched here. This is a pure additive extension — no existing offer.py code
is modified.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PlasticosOfferPriceBridge(models.Model):
    _inherit = "plasticos.offer"

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-fill price_per_lb from match line typical_price when zero/unset on a legacy intake offer."""
        for vals in vals_list:
            if vals.get("match_result_id"):
                # Gate result lineage: no typical-price authority, no autofill.
                continue
            intake_id = vals.get("intake_id")
            buyer_id = vals.get("buyer_id")
            price = vals.get("price_per_lb") or 0.0

            if intake_id and buyer_id and not price:
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
