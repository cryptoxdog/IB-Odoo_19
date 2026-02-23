from odoo import fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    material_profile_ids = fields.One2many(
        "plasticos.material.profile",
        "partner_id",
        string="Material Profiles",
    )

    # ── Navigation: Related Record Counts ──────────────────────
    material_profile_count = fields.Integer(
        string="Profiles",
        compute="_compute_material_profile_count",
    )
    intake_count = fields.Integer(
        string="Intakes",
        compute="_compute_intake_count",
    )

    def _compute_material_profile_count(self):
        """Count material profiles linked to this partner (facility)."""
        Profile = self.env["plasticos.material.profile"]
        for rec in self:
            rec.material_profile_count = Profile.search_count([("partner_id", "=", rec.id)])

    def _compute_intake_count(self):
        """Count intakes linked to this partner (as supplier or facility)."""
        Intake = self.env["plasticos.intake"]
        for rec in self:
            rec.intake_count = Intake.search_count(
                [
                    "|",
                    ("partner_id", "=", rec.id),
                    ("facility_id", "=", rec.id),
                ]
            )

    # ── Navigation Actions (Jump To) ────────────────────────────
    def action_view_material_profiles(self):
        """Navigate to material profiles for this facility."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Material Profiles - {self.name}",
            "res_model": "plasticos.material.profile",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    def action_view_intakes(self):
        """Navigate to intakes for this partner."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes - {self.name}",
            "res_model": "plasticos.intake",
            "view_mode": "list,form",
            "domain": ["|", ("partner_id", "=", self.id), ("facility_id", "=", self.id)],
        }

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.material_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while material profiles exist.")
        return super().write(vals)
