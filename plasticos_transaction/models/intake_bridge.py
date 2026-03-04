from odoo import api, fields, models


class PlasticosIntakeTxBridge(models.Model):
    """Adds transaction reverse navigation to intake."""

    _inherit = "plasticos.intake"

    transaction_ids = fields.One2many(
        "plasticos.transaction",
        "intake_id",
        string="Transactions",
    )
    transaction_count = fields.Integer(
        compute="_compute_transaction_count",
        string="Transaction Count",
    )

    @api.depends("transaction_ids")
    def _compute_transaction_count(self):
        for rec in self:
            rec.transaction_count = len(rec.transaction_ids)

    def action_view_transactions(self):
        """View transactions created from this intake."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": f"Transactions — {self.name}",
            "res_model": "plasticos.transaction",
            "view_mode": "list,form",
            "domain": [("intake_id", "=", self.id)],
            "context": {"default_intake_id": self.id},
        }
        if self.transaction_count == 1:
            action.update(
                {
                    "view_mode": "form",
                    "res_id": self.transaction_ids.id,
                }
            )
        return action
