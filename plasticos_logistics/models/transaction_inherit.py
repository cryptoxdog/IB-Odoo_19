from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosTransactionLoadBridge(models.Model):
    """Add load_id field to transaction (injected by logistics module)."""

    _inherit = "plasticos.transaction"

    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        help="Logistics load linked to this transaction.",
    )

    @api.constrains("load_id", "supplier_id", "buyer_id")
    def _check_load_requires_supplier_buyer(self):
        """Enforce workflow: load cannot be assigned until supplier AND buyer are set."""
        for rec in self:
            if rec.load_id and (not rec.supplier_id or not rec.buyer_id):
                raise ValidationError(
                    "Cannot assign a load until both Supplier and Buyer are selected. "
                    "Please complete the transaction details first."
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
