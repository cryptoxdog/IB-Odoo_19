from odoo import fields, models


class BrokerRetireWizard(models.TransientModel):
    _name = "plasticos.broker.retire.wizard"
    _description = "Retire a Reviewed Broker Knowledge Revision"

    knowledge_id = fields.Many2one("plasticos.broker.knowledge", required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.knowledge_id._retire_with_reason(self.reason)
        return {"type": "ir.actions.act_window_close"}
