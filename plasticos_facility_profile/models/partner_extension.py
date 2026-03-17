from odoo import api, fields, models


class ResPartnerFacilityExtension(models.Model):
    _inherit = "res.partner"

    is_facility_location = fields.Boolean(
        string="Is Facility Location",
        compute="_compute_is_facility_location",
        store=True,
        index=True,
        help=(
            "True when this partner record represents a physical facility location. "
            "True for: (1) any child partner (has parent_id), "
            "or (2) a top-level company with no child partners. "
            "False for: top-level companies that have children (profiles belong to children), "
            "and individual person contacts."
        ),
    )

    @api.depends("parent_id", "is_company", "child_ids")
    def _compute_is_facility_location(self):
        for rec in self:
            if rec.parent_id:
                rec.is_facility_location = True
            elif rec.is_company and not rec.child_ids:
                rec.is_facility_location = True
            else:
                rec.is_facility_location = False
