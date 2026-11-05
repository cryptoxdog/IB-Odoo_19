"""Extend material profile with intake-related fields and actions.

This module adds intake navigation and creation capabilities to
plasticos.material.profile. The extension lives here (in plasticos_intake)
rather than in plasticos_material_profile to avoid circular dependencies.
"""

from odoo import api, fields, models


class PlasticosMaterialProfileIntake(models.Model):
    """Add intake-related fields and actions to material profile."""

    _inherit = "plasticos.material.profile"

    # ── Navigation: Intake Count ──────────────────────────────────
    intake_count = fields.Integer(
        string="Intakes",
        compute="_compute_intake_count",
    )

    @api.depends()
    def _compute_intake_count(self):
        """Count intakes linked to this profile."""
        Intake = self.env["plasticos.intake"]
        for rec in self:
            rec.intake_count = Intake.search_count([("material_profile_id", "=", rec.id)])

    # ── Navigation Actions ────────────────────────────────────────
    def action_view_intakes(self):
        """Navigate to intakes linked to this profile."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes - {self.polymer_id.name}",
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": [("material_profile_id", "=", self.id)],
            "context": {"default_material_profile_id": self.id},
        }

    def action_create_intake(self):
        """Manual ingress: a native Opportunity for this profile's partner when CRM Bridge is installed.

        Without CRM Bridge the legacy intake form stays. No intake is created
        either way until the broker saves.
        """
        self.ensure_one()
        partner = self.partner_id
        route = getattr(partner, "_plasticos_opportunity_action", None) if partner else None
        if callable(route):
            opportunity_action = route(material_profile=self)
            if opportunity_action is not None:
                return opportunity_action
        return {
            "type": "ir.actions.act_window",
            "name": "Create Intake",
            "res_model": "plasticos.intake",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_supplier_id": self.partner_id.parent_id.id
                if self.partner_id.parent_id
                else self.partner_id.id,
                "default_facility_id": self.partner_id.id,
                "default_polymer_id": self.polymer_id.id,
                "default_form_id": self.form_id.id if self.form_id else False,
                "default_color_id": self.color_id.id if self.color_id else False,
                "default_source_type_id": self.source_type_id.id if self.source_type_id else False,
                "default_packaging_type_id": self.packaging_type_id.id if self.packaging_type_id else False,
                "default_material_grade_id": self.material_grade_id.id if self.material_grade_id else False,
                "default_filler_type_id": self.filler_type_id.id if self.filler_type_id else False,
                "default_material_attribute_ids": [(6, 0, self.material_attribute_ids.ids)],
                "default_mfi_value": self.melt_flow_index,
                "default_density_value": self.density,
                "default_moisture_pct": self.moisture_percent,
                "default_contamination_pct": self.contamination_percent,
                "default_material_profile_id": self.id,
            },
        }
