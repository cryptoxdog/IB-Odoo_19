from odoo import api, fields, models
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
    # NOTE: intake_count is added by plasticos_intake module via inheritance

    # ── Computed: Is this partner a facility? ──────────────────
    is_facility = fields.Boolean(
        string="Is Facility",
        compute="_compute_is_facility",
        help="True if this is a facility (has parent) or a standalone company (no children)",
    )

    @api.depends("parent_id", "child_ids")
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

    @api.depends()
    def _compute_material_profile_count(self):
        """Count material profiles linked to this partner (facility)."""
        Profile = self.env["plasticos.material.profile"]
        for rec in self:
            rec.material_profile_count = Profile.search_count([("partner_id", "=", rec.id)])

    # NOTE: action_view_intakes and action_create_intake are added by plasticos_intake module

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

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.material_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while material profiles exist.")
        return super().write(vals)
