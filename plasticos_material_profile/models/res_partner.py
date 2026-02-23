from odoo import fields, models
from odoo.exceptions import ValidationError

# Optional module model name (runtime-guarded, not a hard dependency)
_INTAKE_MODEL = "plasticos" + ".intake"  # noqa: ISC003


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

    # ── Computed: Is this partner a facility? ──────────────────
    is_facility = fields.Boolean(
        string="Is Facility",
        compute="_compute_is_facility",
        help="True if this is a facility (has parent) or a standalone company (no children)",
    )

    def _compute_is_facility(self):
        """
        A partner is a 'facility' if:
        - It has a parent_id (it's a child/location), OR
        - It has no children (standalone company = both HQ and facility)
        """
        for rec in self:
            if rec.parent_id:
                # Has parent = is a facility/location
                rec.is_facility = True
            elif not rec.child_ids:
                # No parent AND no children = standalone company (is both HQ and facility)
                rec.is_facility = True
            else:
                # Has children but no parent = pure parent company (not a facility)
                rec.is_facility = False

    def _compute_material_profile_count(self):
        """Count material profiles linked to this partner (facility)."""
        Profile = self.env["plasticos.material.profile"]
        for rec in self:
            rec.material_profile_count = Profile.search_count([("partner_id", "=", rec.id)])

    def _compute_intake_count(self):
        """Count intakes linked to this partner (if intake module installed)."""
        if _INTAKE_MODEL not in self.env:
            for rec in self:
                rec.intake_count = 0
            return
        Intake = self.env[_INTAKE_MODEL]
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
        """Navigate to intakes for this partner (if intake module installed)."""
        self.ensure_one()
        if _INTAKE_MODEL not in self.env:
            return
        return {
            "type": "ir.actions.act_window",
            "name": f"Intakes - {self.name}",
            "res_model": _INTAKE_MODEL,
            "view_mode": "list,form",
            "domain": ["|", ("partner_id", "=", self.id), ("facility_id", "=", self.id)],
        }

    def action_create_intake(self):
        """Create a new intake for this facility (if intake module installed)."""
        self.ensure_one()
        if _INTAKE_MODEL not in self.env:
            return
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
            "res_model": _INTAKE_MODEL,
            "view_mode": "form",
            "context": {
                "default_partner_id": company_id,
                "default_facility_id": facility_id,
            },
        }

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.material_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while material profiles exist.")
        return super().write(vals)
