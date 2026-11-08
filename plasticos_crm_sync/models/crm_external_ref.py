from odoo import fields, models


class PlasticosCrmExternalRef(models.Model):
    _name = "plasticos.crm.external.ref"
    _description = "CRM External ID Reference"
    _order = "provider, external_id"

    provider = fields.Char(required=True, index=True)
    external_id = fields.Char(required=True, index=True)
    res_model = fields.Char(required=True, index=True, default="crm.lead")
    res_id = fields.Integer(required=True, index=True)
    lead_id = fields.Many2one(
        "crm.lead",
        string="Lead",
        ondelete="cascade",
        index=True,
        help="Convenience link when res_model is crm.lead.",
    )

    _unique_provider_external_model = models.Constraint(
        "unique(provider, external_id, res_model)",
        "External ID already mapped for this provider and model.",
    )
