from odoo import models


class IntakeBrokerMack(models.Model):
    _inherit = "plasticos.intake"

    def action_mack_broker_advice(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": "Mack: Broker Advice",
            "res_model": "plasticos.broker.consultation.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_model": self._name, "default_source_id": self.id},
        }
