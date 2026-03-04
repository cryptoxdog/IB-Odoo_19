from odoo import models


class PlasticosWebLeadBridge(models.Model):
    """Adds intake navigation smart button to web lead."""

    _inherit = "plasticos.web.lead"

    def action_view_intake(self):
        """Navigate to the intake promoted from this web lead."""
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
