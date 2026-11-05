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
        pending = [
            vals
            for vals in vals_list
            if vals.get("intake_id") and vals.get("buyer_id") and not (vals.get("price_per_lb") or 0.0)
        ]
        if pending:
            # One query for every (intake, buyer) pair in the batch. Ordered by
            # typical_price desc, the first line seen per pair is the one the
            # per-pair ``limit=1`` search used to return.
            lines = self.env["plasticos.intake.match"].search(
                [
                    ("intake_id", "in", [vals["intake_id"] for vals in pending]),
                    ("buyer_id", "in", [vals["buyer_id"] for vals in pending]),
                    ("typical_price", ">", 0.0),
                ],
                order="typical_price desc",
            )
            best_line = {}
            for line in lines:
                best_line.setdefault((line.intake_id.id, line.buyer_id.id), line)
            for vals in pending:
                match_line = best_line.get((vals["intake_id"], vals["buyer_id"]))
                if match_line:
                    vals["price_per_lb"] = match_line.typical_price
                    _logger.debug(
                        "offer create: auto-filled price_per_lb=%.4f from match line %s",
                        match_line.typical_price,
                        match_line.id,
                    )
        return super().create(vals_list)
