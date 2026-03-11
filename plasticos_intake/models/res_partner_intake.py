"""Extend res.partner with intake-related fields and actions.


This module adds intake navigation and creation capabilities to
res.partner. The extension lives here (in plasticos_intake)
rather than in plasticos_material_profile to avoid circular dependencies.
"""


from odoo import fields, models


PLASTICOS_INTAKE = "plasticos.intake"

class ResPartnerIntake(models.Model):
    """Add intake-related fields and actions to partner."""

    _inherit = "res.partner"

    # ── Navigation: Intake Count ──────────────────────────────────
    intake_count = fields.Integer(
        string="Intakes",
        compute="_compute_intake_count",
    )

    def _compute_intake_count(self):
        """Count intakes linked to this partner."""
        Intake = self.env[PLASTICOS_INTAKE]
        for rec in self:
            rec.intake_count = Intake.search_count(
                [
                    "|",
                    ("partner_id", "=", rec.id),
                    ("facility_id", "=", rec.id),
                ]
            )

    # ── Navigation Actions ────────────────────────────────────────
    def action_view_intakes(self):
        """Navigate to intakes for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes - {self.name}",
            "res_model": PLASTICOS_INTAKE,
            "view_mode": "list,form",
            "domain": [
                "|",
                ("partner_id", "=", self.id),
                ("facility_id", "=", self.id),
            ],
        }

    def action_create_intake(self):
        """Create a new intake for this facility."""
        self.ensure_one()
        # Determine company and facility
        if self.parent_id:
            # This is a facility under a parent company
            company_id = self.parent_id.id
            facility_id = self.id
        else:
            # Standalone company (both HQ and facility)
            company_id = self.id
            facility_id = self.id

        return {
            "type": "ir.actions.act_window",
            "name": f"New Intake - {self.name}",
            "res_model": PLASTICOS_INTAKE,
            "view_mode": "form",
            "context": {
                "default_partner_id": company_id,
                "default_facility_id": facility_id,
            },
        }
