from markupsafe import Markup

from odoo import SUPERUSER_ID, fields, models


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

        # Propagate material profile from the linked intake when available.
        intake = self.intake_id
        material_profile_id = intake.material_profile_id.id if (intake and intake.material_profile_id) else False

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
            "source_intake_id": intake.id if intake else False,
            # Wire material profile from intake so brokers see the normalised spec.
            "material_profile_id": material_profile_id,
        }

        lead = self.env["crm.lead"].create(vals)
        self.crm_lead_id = lead
        synchronize_images = getattr(lead, "_propagate_available_commercial_images", None)
        if callable(synchronize_images):
            synchronize_images()
        # Use with_user(SUPERUSER_ID) for message_post: auth="none" endpoints leave
        # env.uid=None even after sudo(), causing mail.thread to call _is_public()
        # on an empty res.users() recordset and raise ValueError: Expected singleton.
        self.with_user(SUPERUSER_ID).message_post(  # noqa: SIM117 — sudo() alone does not set uid
            body=Markup("CRM opportunity created: %s") % lead.name,
        )
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
