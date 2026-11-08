import importlib

from odoo import SUPERUSER_ID, fields, models

Markup = importlib.import_module("markupsafe").Markup


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

        The material_profile_id from the linked intake is propagated to the
        crm.lead so brokers can see the normalised material specification
        without navigating to the intake record.

        env.uid fix: the public webhook endpoint uses auth="none" which leaves
        env.uid=None even after sudo(). message_post calls env.user._is_public()
        which requires a singleton. We bind a known uid (SUPERUSER_ID) for all
        mail-thread calls so the author is unambiguous. The crm.lead itself is
        created without an assigned salesperson (user_id=False) as intended.
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
            # HOT is eligibility: the material profile is carried only when the
            # intake already qualified one. Partner stays unlinked until verified.
            "material_profile_id": self.intake_id.material_profile_id.id
            if self.intake_id and self.intake_id.material_profile_id
            else False,
        }

        # auth="none" leaves env.uid empty after sudo(). Lead creation, image
        # sync, and the opportunity note all reach mail.thread, which calls
        # env.user._is_public() and requires a singleton res.users. Bind that
        # sequence to SUPERUSER_ID. The opportunity stays unassigned.
        actor = self.with_user(SUPERUSER_ID)
        lead = actor.env["crm.lead"].create(vals)
        actor.crm_lead_id = lead
        synchronize_images = getattr(lead, "_propagate_available_commercial_images", None)
        if callable(synchronize_images):
            synchronize_images()
        actor.message_post(body=Markup("CRM opportunity created: %s") % lead.name)
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
