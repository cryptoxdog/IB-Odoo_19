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
        existing_facility = self.search([("partner_id", "=", partner.id), ("id", "!=", self.id)], limit=1)
        if existing_facility:
            return self._reconcile_onto_existing_facility(partner, existing_facility)
        materials = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", self.id)])
        conflicts = self._profiles_for_partner(partner, materials)
        for material in materials:
            conflict = conflicts.get((material.polymer_id.id, material.form_id.id or False))
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

    def _profiles_for_partner(self, partner, materials):
        """Partner profiles keyed by polymer and form, excluding the rows being linked."""
        if not materials:
            return {}
        found = self.env["plasticos.material.profile"].search(
            [
                ("id", "not in", materials.ids),
                ("partner_id", "=", partner.id),
                ("polymer_id", "in", materials.polymer_id.ids),
            ]
        )
        return {(row.polymer_id.id, row.form_id.id or False): row for row in found}

    def _reconcile_onto_existing_facility(self, partner, existing_facility):
        """Move this lead's materials onto the location's facility without a second identity."""
        self.ensure_one()
        materials = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", self.id)])
        conflicts = self._profiles_for_partner(partner, materials)
        for material in materials:
            conflict = conflicts.get((material.polymer_id.id, material.form_id.id or False))
            if conflict:
                for line in (material.freeform_notes or "").splitlines():
                    if line and line not in (conflict.freeform_notes or "").splitlines():
                        notes = conflict.freeform_notes or ""
                        conflict.freeform_notes = f"{notes}\n{line}" if notes else line
                material.unlink()
                continue
            material.write({"partner_id": partner.id, "facility_profile_id": existing_facility.id})
        lead = self.crm_lead_id
        self.unlink()
        if lead and not existing_facility.crm_lead_id:
            existing_facility.crm_lead_id = lead
        return existing_facility
