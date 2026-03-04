import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PlasticosWebLeadCrmBridge(models.Model):
    _inherit = "plasticos.web.lead"

    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="CRM Lead",
        index=True,
        ondelete="set null",
        help="CRM lead generated from this web lead.",
    )

    def _create_crm_lead(self):
        """Create a CRM lead from this web lead, if one does not already exist."""
        for rec in self:
            if rec.crm_lead_id:
                continue

            utm_source = self.env["utm.source"].search(
                [("name", "=", "web_lead")], limit=1
            )

            lead_vals = {
                "type": "lead",
                "name": rec.company_name or rec.contact_name or "Web Lead",
                "partner_name": rec.company_name or False,
                "contact_name": rec.contact_name or False,
                "email_from": rec.contact_email or False,
                "phone": rec.contact_phone or False,
                "description": rec.material_description or False,
                "partner_id": rec.partner_id.id if rec.partner_id else False,
            }
            if utm_source:
                lead_vals["source_id"] = utm_source.id

            lead = self.env["crm.lead"].create(lead_vals)
            rec.crm_lead_id = lead.id
            rec.message_post(
                body=f"CRM Lead <b>{lead.name}</b> (ID: {lead.id}) created.",
            )
