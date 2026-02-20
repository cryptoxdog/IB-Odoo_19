from odoo import models, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    facility_profile_ids = fields.One2many(
        "plasticos.facility.profile",
        "partner_id",
        string="Facility Capabilities"
    )

    x_facility_role = fields.Selection([
        ("processor", "Processor"),
        ("broker", "Broker"),
        ("manufacturer", "Manufacturer"),
        ("mrf", "MRF"),
        ("compounder", "Compounder"),
        ("other", "Other"),
    ])

    x_preferred_contact_id = fields.Many2one(
        "res.partner",
        string="Preferred Contact",
        help="Last-selected contact for this company/facility. "
             "Auto-populated when a user selects a contact on an intake. "
             "Used to auto-fill contact on subsequent intakes.",
    )

    def write(self, vals):
        if "parent_id" in vals and not vals.get("parent_id"):
            for rec in self:
                if rec.facility_profile_ids:
                    raise ValidationError(
                        "Cannot convert facility to parent while "
                        "capability profile exists."
                    )
        return super().write(vals)
