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
        """Retired as an offer-creation authority.

        Offers are created from reviewed Gate match results on the native
        Opportunity (one matching command, one offer path). The selected
        intake match lines and their typical price carry no commercial
        authority, so this action no longer creates offers from them.
        """
        self.ensure_one()
        self._assert_status("matched")
        if not self.partner_id:
            raise UserError("Cannot send offers without a supplier. Set the Company on this intake first.")
        _logger.info("Intake %s: offer creation from match lines is retired; use the Opportunity.", self.id)
        raise UserError(
            "Offers are created from reviewed Gate match results on the Opportunity "
            "(Match via Gate, review results, Create Offers). Selected match lines are display only."
        )
