from odoo import api, fields, models


class PlasticosMaterialProfileCapability(models.Model):
    """Link a material profile to the line it enters or leaves.

    Direction stays on the material-profile module. This inherit only adds the
    line and the feedstock rate.
    """

    _inherit = "plasticos.material.profile"

    capability_id = fields.Many2one(
        "plasticos.capability",
        string="Capability",
        ondelete="set null",
        index=True,
        help="The line this material enters or leaves. Blank when a person leaves it unset.",
    )
    rate_lb_hr = fields.Float(
        string="Rate (lb/hr)",
        help="How fast this material goes through its capability. Throughput depends on the feedstock.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "capability_id" not in vals:
                sole = self._sole_capability_id(vals.get("partner_id"))
                if sole:
                    vals["capability_id"] = sole
        return super().create(vals_list)

    @api.model
    def _sole_capability_id(self, partner_id):
        """The site's only capability, or False when it has none or more than one."""
        if not partner_id:
            return False
        partner = self.env["res.partner"].browse(partner_id)
        capabilities = partner.facility_profile_ids.capability_ids
        if len(capabilities) == 1:
            return capabilities.id
        return False
