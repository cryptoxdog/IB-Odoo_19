from markupsafe import Markup

from odoo import fields, models


class PlasticosWebLeadCRM(models.Model):
    _inherit = "plasticos.web.lead"

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="set null",
    )

    def _create_crm_lead(self):
        """Called after HOT classification — creates one native crm.lead opportunity.

        HOT is a triage signal, not broker approval: the opportunity starts in
        the seeded non-Won ``New`` stage, stays unassigned, and never creates a
        partner. Submitted facts are copied as-is; estimates are labelled.
        """
        self.ensure_one()
        if self.crm_lead_id:
            return self.crm_lead_id

        ref = self.env.ref
        source = self.lead_source_id or ref("plasticos_crm_bridge.utm_source_web_lead", raise_if_not_found=False)
        stage = ref("plasticos_crm_bridge.stage_new", raise_if_not_found=False)

        vals = {
            "name": " — ".join(filter(None, [self.company_name, self.material_description])) or "Web Lead",
            "partner_name": self.company_name,
            "contact_name": self.contact_name,
            "email_from": self.contact_email,
            "phone": self.contact_phone,
            "description": self._crm_opportunity_description(),
            "source_id": source.id if source else False,
            "type": "opportunity",
            "stage_id": stage.id if stage else False,
            # Never the webhook technical user; an operator assigns a salesperson.
            "user_id": False,
            # Only an already-linked partner is kept; none is created here.
            "partner_id": self.partner_id.id if self.partner_id else False,
            "source_intake_id": self.intake_id.id if self.intake_id else False,
        }

        lead = self.env["crm.lead"].create(vals)
        self.crm_lead_id = lead
        synchronize_images = getattr(lead, "_propagate_available_commercial_images", None)
        if callable(synchronize_images):
            synchronize_images()
        self.message_post(body=Markup("CRM opportunity created: %s") % lead.name)
        return lead

    def _crm_opportunity_description(self):
        """HTML-escaped summary of submitted facts; computed estimates are labelled, empty values omitted."""
        self.ensure_one()
        payload = self.canonical_payload or {}
        pickup = " ".join(filter(None, [payload.get("pickup_location_text"), payload.get("pickup_postal_code")]))
        rows = [
            ("Material (submitted)", self.material_description),
            ("Quantity (submitted)", payload.get("quantity_text")),
            ("Weight per load (submitted)", payload.get("weight_per_load_text")),
            ("Frequency (submitted)", payload.get("frequency_text") or self.frequency),
            ("Contaminants (submitted)", payload.get("contaminants_text") or self.contaminant_notes),
            ("Pickup location (submitted)", pickup),
            ("Est. lbs per load (computed)", self.estimated_lbs_per_load or None),
            ("Est. loads per month (computed)", self.estimated_loads_per_month or None),
        ]
        items = [Markup("<li><b>%s:</b> %s</li>") % (label, value) for label, value in rows if value]
        return Markup("<ul>%s</ul>") % Markup("").join(items) if items else False
