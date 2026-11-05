"""Extend res.partner with intake-related fields and actions.

This module adds intake navigation and creation capabilities to
res.partner. The extension lives here (in plasticos_intake)
rather than in plasticos_material_profile to avoid circular dependencies.
"""

from odoo import api, fields, models


class ResPartnerIntake(models.Model):
    """Add intake-related fields and actions to partner."""

    _inherit = "res.partner"

    # ── Navigation: Intake Count ──────────────────────────────────
    intake_count = fields.Integer(
        string="Intakes",
        compute="_compute_intake_count",
    )

    @api.depends()
    def _compute_intake_count(self):
        """Count intakes linked to this partner."""
        Intake = self.env["plasticos.intake"]
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
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": [
                "|",
                ("partner_id", "=", self.id),
                ("facility_id", "=", self.id),
            ],
        }

    def _plasticos_opportunity_action(self, material_profile=None):
        """The native Opportunity route when CRM Bridge is installed; None otherwise.

        Manual ingress starts from a verified Partner. It opens an Opportunity
        form preset with the partner (and profile); no intake is synthesized.
        """
        self.ensure_one()
        if "crm.lead" not in self.env:
            return None
        opener = getattr(self.env["crm.lead"], "_plasticos_manual_opportunity_action", None)
        if not callable(opener):
            return None
        return opener(partner=self, material_profile=material_profile)

    def action_create_intake(self):
        """Manual ingress: a native Opportunity for this partner when CRM Bridge is installed, else an intake form."""
        self.ensure_one()
        opportunity_action = self._plasticos_opportunity_action()
        if opportunity_action is not None:
            return opportunity_action
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
            "res_model": "plasticos.intake",
            "view_mode": "form",
            "context": {
                "default_partner_id": company_id,
                "default_facility_id": facility_id,
            },
        }
