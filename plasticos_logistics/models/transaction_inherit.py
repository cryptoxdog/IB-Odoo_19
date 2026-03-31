from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosTransactionLoadBridge(models.Model):
    """Add load_id field to transaction (injected by logistics module)."""

    _inherit = "plasticos.transaction"

    load_id = fields.Many2one(
        "plasticos.load",
        string="Load",
        help="Logistics load linked to this transaction.",
        index=True,
        ondelete="cascade",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to update reverse link on load."""
        records = super().create(vals_list)
        # Update transaction_id on linked loads
        loads_to_update = records.filtered(lambda r: r.load_id).mapped("load_id")
        if loads_to_update:
            loads_to_update._compute_transaction_id()
        return records

    def write(self, vals):
        """Override write to update reverse link on load when load_id changes."""
        old_loads = self.env["plasticos.load"]
        if "load_id" in vals:
            # Capture old loads before write
            old_loads = self.filtered(lambda r: r.load_id).mapped("load_id")

        res = super().write(vals)

        if "load_id" in vals:
            # Recompute transaction_id on old loads (now unlinked)
            if old_loads:
                old_loads._compute_transaction_id()
            # Recompute transaction_id on new loads
            new_loads = self.filtered(lambda r: r.load_id).mapped("load_id")
            if new_loads:
                new_loads._compute_transaction_id()

        return res

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
