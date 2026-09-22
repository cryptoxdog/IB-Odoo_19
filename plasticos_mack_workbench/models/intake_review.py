"""Canonical-intake projection for Mack internal review receipts."""

from odoo import api, fields, models


class PlasticosIntake(models.Model):
    """Expose immutable Mack review records on their canonical intake."""

    _inherit = "plasticos.intake"

    mack_review_request_ids = fields.One2many(
        "plasticos.mack.internal.review",
        "intake_id",
        string="Mack Internal Review Requests",
        readonly=True,
    )
    mack_review_request_count = fields.Integer(compute="_compute_mack_review_request_count")

    @api.depends("mack_review_request_ids")
    def _compute_mack_review_request_count(self):
        for intake in self:
            intake.mack_review_request_count = len(intake.mack_review_request_ids)

    def action_view_mack_review_requests(self):
        self.ensure_one()
        action = self.env.ref("plasticos_mack_workbench.action_mack_internal_review").read()[0]
        action["domain"] = [("intake_id", "=", self.id)]
        action["context"] = {"default_intake_id": self.id}
        return action
