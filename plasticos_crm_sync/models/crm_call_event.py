from odoo import fields, models


class PlasticosCrmCallEvent(models.Model):
    _name = "plasticos.crm.call.event"
    _description = "CRM Call History Event"
    _order = "call_datetime_utc desc, id desc"

    provider = fields.Char(required=True, index=True)
    external_id = fields.Char(required=True, index=True)
    lead_id = fields.Many2one(
        "crm.lead",
        string="Lead",
        ondelete="set null",
        index=True,
    )
    contact_external_id = fields.Char(index=True)
    call_datetime_utc = fields.Datetime(index=True)
    duration_seconds = fields.Integer(default=0)
    user_name = fields.Char()
    result_code = fields.Char(index=True)
    comment = fields.Text()

    _unique_provider_external = models.Constraint(
        "unique(provider, external_id)",
        "Call event already imported for this provider.",
    )
