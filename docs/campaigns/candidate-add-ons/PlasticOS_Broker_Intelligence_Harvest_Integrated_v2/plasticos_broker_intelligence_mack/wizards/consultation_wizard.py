import json

from odoo import fields, models


class ConsultationWizard(models.TransientModel):
    _name = "plasticos.broker.consultation.wizard"
    _description = "Mack: Broker Advice"

    source_model = fields.Selection(
        [
            ("plasticos.intake", "Intake"),
            ("plasticos.web.lead", "Web Lead"),
            ("plasticos.offer", "Offer"),
            ("plasticos.match.result", "Match Result"),
        ],
        required=True,
    )
    source_id = fields.Integer(required=True)
    question = fields.Text(required=True, default="What information is missing before we can quote this material?")
    source_message_id = fields.Many2one("mail.message", string="Authenticated Chatter Source (optional)")
    consultation_id = fields.Many2one("plasticos.broker.consultation", readonly=True)
    response = fields.Text(readonly=True)

    def action_consult(self):
        self.ensure_one()
        receipt = self.env["plasticos.broker.consultation"].action_consult(
            self.source_model, self.source_id, self.question, self.source_message_id.id or None
        )
        self.consultation_id = receipt.id
        self.response = json.dumps(receipt.response_snapshot, ensure_ascii=False, indent=2, default=str)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
