from odoo import fields, models


class PlasticosMatchResultTxBridge(models.Model):
    """Adds transaction_id back-link to match result."""

    _inherit = "plasticos.match.result"

    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        tracking=True,
        ondelete="set null",
        help="Transaction created from this match.",
    )

    def action_view_transaction(self):
        """Navigate to the transaction from this match result."""
        self.ensure_one()
        if not self.transaction_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Transaction — {self.transaction_id.name}",
            "res_model": "plasticos.transaction",
            "view_mode": "form",
            "res_id": self.transaction_id.id,
        }
