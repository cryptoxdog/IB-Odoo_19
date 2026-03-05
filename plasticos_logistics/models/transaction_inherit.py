from odoo import fields, models


class PlasticosTransactionLoadBridge(models.Model):
    """Add load_id field to transaction (injected by logistics module)."""

    _inherit = "plasticos.transaction"

    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        help="Logistics load linked to this transaction.",
    )

    def action_view_load(self):
        """Open the linked load form."""
        self.ensure_one()
        if not self.load_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "plasticos.load",
            "res_id": self.load_id.id,
            "view_mode": "form",
            "target": "current",
        }
