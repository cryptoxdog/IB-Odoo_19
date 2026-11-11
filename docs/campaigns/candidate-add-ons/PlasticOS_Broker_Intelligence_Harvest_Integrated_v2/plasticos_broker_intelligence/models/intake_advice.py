"""Read-only advice affordance on the canonical intake; never routes or writes it."""

from odoo import models


class BrokerIntakeAdvice(models.Model):
    _inherit = "plasticos.intake"

    def action_broker_advice(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": "Broker Advice",
            "res_model": "plasticos.broker.advice.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_model": self._name, "default_source_id": self.id},
        }
