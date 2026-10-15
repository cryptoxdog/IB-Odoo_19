from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

# Stored references that must follow a material row when two identities collapse.
_MATERIAL_REFERENCES = (
    ("plasticos.intake", "material_profile_id"),
    ("sale.order.line", "material_profile_id"),
    ("purchase.order.line", "material_profile_id"),
    ("crm.lead", "material_profile_id"),
    ("plasticos.transaction", "supplier_profile_id"),
    ("plasticos.transaction", "buyer_profile_id"),
    ("plasticos.transaction", "supplier_material_id"),
)
_MERGE_IGNORE = {
    "id",
    "display_name",
    "partner_id",
    "facility_profile_id",
    "polymer_id",
    "form_id",
    "company_id",
    "create_uid",
    "create_date",
    "write_uid",
    "write_date",
    "active",
}


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

    associated_lead_ids = fields.One2many(
        "crm.lead",
        "facility_profile_id",
        string="Associated CRM Leads",
        help="Leads that resolved to this facility. The provisional owner remains crm_lead_id.",
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
        if not partner or not partner.is_company or not partner.is_facility:
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
        self._remember_lead(self.crm_lead_id)
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

    def _remember_lead(self, lead):
        """Point a lead at this facility without taking another lead's provisional ownership."""
        self.ensure_one()
        if not lead:
            return
        current = lead.facility_profile_id
        if (
            current
            and current != self
            and current.partner_id
            and self.partner_id
            and current.partner_id != self.partner_id
        ):
            raise ValidationError("This lead is already associated with a different facility.")
        if current != self:
            lead.facility_profile_id = self.id

    def _reconcile_onto_existing_facility(self, partner, existing_facility):
        """Move this lead's materials onto the location's one facility profile.

        A polymer and form that already exist are merged only when every stored
        value can be kept. A real conflict leaves both profiles in place.
        """
        self.ensure_one()
        materials = self.env["plasticos.material.profile"].search([("facility_profile_id", "=", self.id)])
        conflicts = self._profiles_for_partner(partner, materials)
        planned = []
        for material in materials:
            conflict = conflicts.get((material.polymer_id.id, material.form_id.id or False))
            if not conflict:
                planned.append((material, None, None))
                continue
            updates, problems = self._merge_plan(conflict, material)
            if problems:
                raise ValidationError(
                    f"Location '{partner.name}' already has a {material.polymer_id.name} profile "
                    f"and {', '.join(problems)} cannot be combined. The lead-owned profile was kept."
                )
            planned.append((material, conflict, updates))
        for material, conflict, updates in planned:
            if conflict is None:
                material.write({"partner_id": partner.id, "facility_profile_id": existing_facility.id})
                continue
            if updates:
                conflict.write(updates)
            self._retarget_material_references(material, conflict)
            material.unlink()
        lead = self.crm_lead_id
        existing_facility._remember_lead(lead)
        if existing_facility.crm_lead_id:
            existing_facility._remember_lead(existing_facility.crm_lead_id)
        self.unlink()
        if lead and not existing_facility.crm_lead_id:
            existing_facility.crm_lead_id = lead
        return existing_facility

    def _merge_plan(self, survivor, provisional):
        """Return ``(updates, conflicts)`` without writing."""
        updates = {}
        problems = []
        for name, field in provisional._fields.items():
            if name in _MERGE_IGNORE or not field.store or field.compute or field.related:
                continue
            if field.type in ("one2many", "binary", "html", "reference"):
                continue
            incoming = provisional[name]
            current = survivor[name]
            if field.type == "many2many":
                missing = incoming - current
                if missing:
                    updates[name] = [Command.link(row.id) for row in missing]
                continue
            if field.type == "many2one":
                if not incoming:
                    continue
                if not current:
                    updates[name] = incoming.id
                elif current != incoming:
                    problems.append(field.string or name)
                continue
            if field.type in ("char", "text", "selection"):
                if not incoming:
                    continue
                if not current:
                    updates[name] = incoming
                elif field.type == "text":
                    lines = (current or "").splitlines()
                    extra = [line for line in str(incoming).splitlines() if line and line not in lines]
                    if extra:
                        updates[name] = f"{current}\n" + "\n".join(extra) if current else "\n".join(extra)
                elif current != incoming:
                    problems.append(field.string or name)
                continue
            if field.type in ("float", "integer", "monetary"):
                if not incoming:
                    continue
                if not current:
                    updates[name] = incoming
                elif current != incoming:
                    problems.append(field.string or name)
                continue
            if field.type == "boolean":
                if incoming and not current:
                    updates[name] = True
                continue
            if incoming and incoming != current:
                problems.append(field.string or name)
        return updates, problems

    def _retarget_material_references(self, source, target):
        """Move stored foreign keys onto the surviving material profile."""
        for model_name, field_name in _MATERIAL_REFERENCES:
            self._retarget_one_reference(source, target, model_name, field_name)

    def _retarget_one_reference(self, source, target, model_name, field_name):
        if model_name not in self.env:
            return
        model = self.env[model_name]
        field = model._fields.get(field_name)
        if field is None or not field.store or field.compute:
            return
        rows = model.search([(field_name, "=", source.id)])
        if rows:
            rows.write({field_name: target.id})
