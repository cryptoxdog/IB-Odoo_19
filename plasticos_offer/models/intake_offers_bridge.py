from odoo import api, fields, models


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
