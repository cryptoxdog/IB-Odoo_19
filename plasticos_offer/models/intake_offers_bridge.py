import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PlasticosIntakeOffersBridge(models.Model):
    """Adds offer reverse navigation to intake."""

    _inherit = "plasticos.intake"

    offer_ids = fields.One2many(
        "plasticos.offer",
        "intake_id",
        string="Offers",
    )
    offer_count = fields.Integer(
        compute="_compute_offer_count",
        string="Offer Count",
    )

    @api.depends("offer_ids")
    def _compute_offer_count(self):
        for rec in self:
            rec.offer_count = len(rec.offer_ids)

    def action_view_offers(self):
        """View offers sent from this intake."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Offers — {self.name}",
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
        }

    def action_send_offers(self):
        """Create plasticos.offer records for each selected match line."""
        self.ensure_one()
        self._assert_status("matched")
        selected = self.match_line_ids.filtered("selected")
        if not selected:
            raise UserError("Please select at least one buyer to send offers to.")

        if not self.partner_id:
            raise UserError("Cannot send offers without a supplier. Set the Company on this intake first.")

        offer_vals = []
        for match in selected:
            if not match.buyer_id:
                _logger.warning(
                    "Skipping match line %s — no buyer_id set (buyer_name=%s)",
                    match.id,
                    match.buyer_name,
                )
                continue
            offer_vals.append(
                {
                    "intake_id": self.id,
                    "supplier_id": self.partner_id.id,
                    "buyer_id": match.buyer_id.id,
                    "price_per_lb": match.typical_price or 0.0,
                    "quantity_lbs": float(self.quantity_per_load_lbs or 0),
                }
            )

        if not offer_vals:
            raise UserError(
                "No offers were created. Ensure selected buyer match lines have a Buyer set.\n\n"
                "Use the bulk assign wizard to assign buyers to unresolved match lines."
            )

        offers_created = self.env["plasticos.offer"].create(offer_vals)

        self.status = "offer_sent"
        self.message_post(
            body=(
                f"Offers sent to {len(offers_created)} buyer(s): {', '.join(offers_created.mapped('buyer_id.name'))}"
            ),
            message_type="notification",
            subtype_xmlid="mail.mt_note",
        )

        return {
            "type": "ir.actions.act_window",
            "name": "Offers Created",
            "res_model": "plasticos.offer",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "target": "current",
        }
