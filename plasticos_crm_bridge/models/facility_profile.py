from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

_PROFILE_MODEL = "plasticos.material.profile"
_UNMERGED_FIELD_TYPES = frozenset(("one2many", "binary", "html", "reference"))
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
    material_profile_ids = fields.One2many(
        "plasticos.material.profile",
        "facility_profile_id",
        string="Material Profiles",
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
            blocked = self._blocked_reference_labels(material) + self._blocked_binding_labels(material)
            if blocked:
                raise ValidationError(
                    f"Location '{partner.name}' already has a {material.polymer_id.name} profile "
                    f"and {', '.join(blocked)} cannot be moved. The lead-owned profile was kept."
                )
            planned.append((material, conflict, updates))
        for material, conflict, updates in planned:
            if conflict is None:
                material.write({"partner_id": partner.id, "facility_profile_id": existing_facility.id})
                continue
            if updates:
                conflict.write(updates)
            self._retarget_material_references(material, conflict)
            self._retarget_profile_bindings(material, conflict)
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
            if field.type in _UNMERGED_FIELD_TYPES:
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

    @api.model
    def ensure_canonical_facility(self, partner, lead):
        """Return the one facility profile for a verified location.

        A missing profile is created for that partner. Material profiles already
        stored on the partner are attached to it. No child partner is created.
        """
        if not partner or not partner.is_facility:
            raise ValidationError("A verified facility location is required.")
        located = self.search([("partner_id", "=", partner.id)])
        if len(located) > 1:
            raise ValidationError("This location has more than one facility profile.")
        if not located:
            located = self.create({"partner_id": partner.id, "crm_lead_id": lead.id})
        loose = self.env[_PROFILE_MODEL].search([("partner_id", "=", partner.id), ("facility_profile_id", "=", False)])
        if loose:
            loose.write({"facility_profile_id": located.id})
        located._remember_lead(lead)
        return located

    def _profile_reference_fields(self):
        """Installed stored many2one and many2many fields that point at a material profile."""
        found = []
        for model_name in self.env.registry:
            if model_name == _PROFILE_MODEL:
                continue
            model = self.env[model_name]
            if not model._auto:
                continue
            for field in model._fields.values():
                if field.comodel_name != _PROFILE_MODEL or field.type not in ("many2one", "many2many"):
                    continue
                if not field.store:
                    continue
                found.append(field)
        return found

    def _rows_for_reference(self, source, field):
        if field.type == "many2one":
            return self.env[field.model_name].search([(field.name, "=", source.id)])
        return self.env[field.model_name].search([(field.name, "in", source.ids)])

    def _blocked_reference_labels(self, source):
        """Computed references cannot be rewritten, so a dependent row blocks deletion."""
        labels = []
        for field in self._profile_reference_fields():
            if not field.compute and not field.related:
                continue
            if self._rows_for_reference(source, field):
                labels.append(f"{field.model_name}.{field.name}")
        return labels

    def _retarget_material_references(self, source, target):
        """Move every writable installed foreign key onto the surviving material profile."""
        for field in self._profile_reference_fields():
            if field.compute or field.related:
                continue
            self._retarget_one_field(source, target, field)

    def _retarget_one_field(self, source, target, field):
        rows = self._rows_for_reference(source, field)
        if not rows:
            return
        if field.type == "many2one":
            rows.write({field.name: target.id})
            return
        rows.write({field.name: [Command.unlink(source.id), Command.link(target.id)]})

    def _blocked_binding_labels(self, source):
        """Records mail.thread deletes by model and id, when that row cannot be retargeted."""
        if "mail.scheduled.message" not in self.env:
            return []
        scheduled = self.env["mail.scheduled.message"].search(
            [("model", "=", _PROFILE_MODEL), ("res_id", "=", source.id)],
            limit=1,
        )
        if not scheduled:
            return []
        return ["mail.scheduled.message"]

    def _retarget_profile_bindings(self, source, target):
        """Keep images, chatter, and follower subscriptions on the surviving profile."""
        attachments = self.env["ir.attachment"].search([("res_model", "=", _PROFILE_MODEL), ("res_id", "=", source.id)])
        if attachments:
            attachments.write({"res_id": target.id})
        messages = self.env["mail.message"].search([("model", "=", _PROFILE_MODEL), ("res_id", "=", source.id)])
        if messages:
            messages.write({"res_id": target.id})
        self._retarget_followers(source, target)

    def _retarget_followers(self, source, target):
        """Move subscriptions onto the survivor without a second row for the same partner.

        A partner already following the survivor keeps that row. Missing subtypes are
        added. Subtypes the survivor already has are left as they are.
        """
        followers = self.env["mail.followers"].sudo()  # sudo: sync ACL cannot read follower rows
        source_rows = followers.search([("res_model", "=", _PROFILE_MODEL), ("res_id", "=", source.id)])
        if not source_rows:
            return
        target_rows = followers.search([("res_model", "=", _PROFILE_MODEL), ("res_id", "=", target.id)])
        target_by_partner = {row.partner_id.id: row for row in target_rows}
        for row in source_rows:
            kept = target_by_partner.get(row.partner_id.id)
            if kept is None:
                row.write({"res_id": target.id})
                continue
            missing = row.subtype_ids - kept.subtype_ids
            if missing:
                kept.write({"subtype_ids": [Command.link(subtype.id) for subtype in missing]})
            row.unlink()
