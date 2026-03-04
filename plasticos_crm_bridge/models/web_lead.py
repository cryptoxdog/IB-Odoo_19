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
        """Called after HOT classification — creates crm.lead with web_lead source."""
        self.ensure_one()
        if self.crm_lead_id:
            return self.crm_lead_id

        # Resolve lead_source_id record
        LeadSource = self.env["utm.source"]
        source = LeadSource.search([("name", "=", "web_lead")], limit=1)

        vals = {
            "name": f"{self.company_name} — {self.material_description or 'Web Lead'}",
            "partner_name": self.company_name,
            "contact_name": self.contact_name,
            "email_from": self.contact_email,
            "phone": self.contact_phone,
            "description": self.material_description,
            "source_id": source.id if source else False,
            "type": "lead",
            # Link to partner if already created
            "partner_id": self.partner_id.id if self.partner_id else False,
        }

        lead = self.env["crm.lead"].create(vals)
        self.crm_lead_id = lead
        self.message_post(body=f"CRM Lead created: {lead.name}")
        return lead
