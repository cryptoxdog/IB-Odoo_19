from odoo import fields, models


class ResPartnerCrmSync(models.Model):
    _inherit = "res.partner"

    crm_call_event_ids = fields.One2many(
        "plasticos.crm.call.event",
        "partner_id",
        string="CRM Call History",
    )
    crm_external_table_row_ids = fields.One2many(
        "plasticos.crm.external.table.row",
        "partner_id",
        string="CRM Custom Table Rows",
    )
