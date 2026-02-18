from odoo import models, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    material_profile_ids = fields.One2many(
        "plasticos.material.profile",
        "partner_id",
        string="Material Profiles"
    )

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.material_profile_ids:
                    raise ValidationError("Cannot convert facility to parent while material profiles exist.")
        return super().write(vals)
