"""Read-only native intake projection for Mack chat intent receipts."""

from odoo import api, fields, models


class PlasticosIntake(models.Model):
    """Expose immutable native-chat intent receipts on the canonical intake."""

    _inherit = "plasticos.intake"

    mack_chat_intent_receipt_ids = fields.One2many(
        "plasticos.mack.chat.intent.receipt",
        "intake_id",
        string="Mack Chat Intent Receipts",
        readonly=True,
    )
    mack_chat_intent_receipt_count = fields.Integer(compute="_compute_mack_chat_intent_receipt_count")

    @api.depends("mack_chat_intent_receipt_ids")
    def _compute_mack_chat_intent_receipt_count(self):
        for intake in self:
            intake.mack_chat_intent_receipt_count = len(intake.mack_chat_intent_receipt_ids)

    def action_view_mack_chat_intent_receipts(self):
        self.ensure_one()
        action = self.env.ref("plasticos_mack_workbench.action_mack_chat_intent_receipt").read()[0]
        action["domain"] = [("intake_id", "=", self.id)]
        action["context"] = {"default_intake_id": self.id}
        return action
