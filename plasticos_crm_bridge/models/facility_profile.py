from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FacilityProfileCrmOwnership(models.Model):
    _inherit = "plasticos.facility.profile"

    partner_id = fields.Many2one(required=False)
    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="restrict",
        help="VanillaSoft lead that owns this facility profile until a verified location is linked.",
    )

    _unique_crm_lead = models.Constraint(
        "unique(crm_lead_id)",
        "A CRM lead may own only one facility profile.",
    )

    @api.constrains("partner_id", "crm_lead_id")
    def _check_crm_or_partner_owner(self):
        for rec in self:
            if rec.partner_id or rec.crm_lead_id:
                continue
            raise ValidationError("A facility profile needs a facility partner or a CRM lead.")

    def link_verified_location(self, partner):
        """Attach this lead-owned facility and its materials to a verified location.

        The same facility profile and material profile rows are kept.
        """
        self.ensure_one()
        if not partner or not partner.parent_id or not partner.is_company:
            raise ValidationError("A verified facility location is required.")
        if self.partner_id and self.partner_id != partner:
            raise ValidationError("This facility profile is already linked to a different location.")
        materials = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", self.id)])
        for material in materials:
            conflict = self.env["plasticos.material.profile"].search(
                [
                    ("id", "!=", material.id),
                    ("partner_id", "=", partner.id),
                    ("polymer_id", "=", material.polymer_id.id),
                    ("form_id", "=", material.form_id.id or False),
                ],
                limit=1,
            )
            if conflict:
                raise ValidationError(
                    f"Location '{partner.name}' already has a {material.polymer_id.name} profile. "
                    "The lead-owned profile was kept."
                )
        if self.partner_id != partner:
            self.partner_id = partner.id
        if materials:
            materials.write({"partner_id": partner.id})
        return self
