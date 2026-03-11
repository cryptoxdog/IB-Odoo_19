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
        """Open intake form pre-filled from this material profile."""
        self.ensure_one()
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
                "default_origin_form_id": self.origin_form_id.id if self.origin_form_id else False,
                "default_filler_type_id": self.filler_type_id.id if self.filler_type_id else False,
                "default_material_attribute_ids": [(6, 0, self.material_attribute_ids.ids)],
                "default_mfi_value": self.melt_flow_index,
                "default_density_value": self.density,
                "default_moisture_pct": self.moisture_percent,
                "default_contamination_pct": self.contamination_percent,
                "default_has_metal": self.has_metal,
                "default_has_fr": self.has_fr,
                "default_material_profile_id": self.id,
            },
        }
