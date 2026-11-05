"""Collect the mandatory reason for one historical reopen."""

from odoo import fields, models

PLASTICOS_TRANSACTION = "plasticos.transaction"


class PlasticosTransactionReopenWizard(models.TransientModel):
    _name = "plasticos.transaction.reopen.wizard"
    _description = "Reopen One Historical Transaction"

    transaction_id = fields.Many2one(PLASTICOS_TRANSACTION, required=True, ondelete="cascade")
    reason = fields.Text(required=True)

    def action_reopen(self):
        self.ensure_one()
        self.transaction_id.action_reopen_historical(self.reason)
        return {"type": "ir.actions.act_window_close"}
