"""Transient on-demand, side-effect-free operator advisory."""

import json

from odoo import fields, models


class BrokerAdviceWizard(models.TransientModel):
    _name = "plasticos.broker.advice.wizard"
    _description = "Broker Advice on an Existing Record"

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
    question = fields.Text(required=True, default="What evidence is missing before the next human decision?")
    result = fields.Text(readonly=True)

    def action_get_advice(self):
        self.ensure_one()
        advice = self.env["plasticos.broker.advice.service"].advise_v2(self.source_model, self.source_id, self.question)
        self.result = json.dumps(advice, ensure_ascii=False, indent=2, default=str)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
