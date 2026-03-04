from odoo import fields, models


class PlasticosTransactionBridge(models.Model):
    """Adds intake origin navigation to transaction."""

    _inherit = "plasticos.transaction"

    # ── Forward: intake this transaction originated from ─────
    intake_id = fields.Many2one(
        "plasticos.intake",
        string="Source Intake",
        index=True,
        tracking=True,
        ondelete="set null",
        help="Intake that originated this transaction.",
    )

    # ── Navigation ───────────────────────────────────────────
    def action_view_intake(self):
        """Jump to the source intake."""
        self.ensure_one()
        if not self.intake_id:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Intake — {self.intake_id.name}",
            "res_model": "plasticos.intake",
            "view_mode": "form",
            "res_id": self.intake_id.id,
        }
