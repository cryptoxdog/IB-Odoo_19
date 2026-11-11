from odoo import models


class BrokerMatchRejection(models.Model):
    _inherit = "plasticos.match.result"

    def action_broker_rejection_advice(self):
        self.ensure_one()
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": "Match Rejection Advice",
            "res_model": "plasticos.broker.rejection.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_source_model": self._name, "default_source_id": self.id},
        }
