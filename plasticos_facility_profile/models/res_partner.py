from odoo import api, models, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    facility_profile_ids = fields.One2many(
        "plasticos.facility.profile",
        "partner_id",
        string="Facility Capabilities"
    )

    partner_type_id = fields.Many2one(
        "plasticos.partner.type",
        string="Partner Type",
        help="Canonical partner/facility type from master registry.",
    )

    # Backward-compatible computed Selection field
    x_facility_role = fields.Selection(
        selection=[
            ("processor", "Processor"),
            ("broker", "Broker"),
            ("manufacturer", "Manufacturer"),
            ("mrf", "MRF"),
            ("compounder", "Compounder"),
            ("recycler", "Recycler"),
            ("distributor", "Distributor"),
            ("carrier", "Carrier"),
            ("other", "Other"),
        ],
        compute="_compute_x_facility_role",
        inverse="_inverse_x_facility_role",
        store=True,
    )

    @api.depends("partner_type_id", "partner_type_id.code")
    def _compute_x_facility_role(self):
        for rec in self:
            rec.x_facility_role = rec.partner_type_id.code if rec.partner_type_id else False

    def _inverse_x_facility_role(self):
        PartnerType = self.env["plasticos.partner.type"]
        for rec in self:
            if rec.x_facility_role:
                partner_type = PartnerType.search(
                    [("code", "=", rec.x_facility_role)], limit=1
                )
                rec.partner_type_id = partner_type.id if partner_type else False
            else:
                rec.partner_type_id = False

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
