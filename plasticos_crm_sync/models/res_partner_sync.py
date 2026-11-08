from odoo import fields, models


class ResPartnerCrmSync(models.Model):
    _inherit = "res.partner"

    crm_call_event_ids = fields.One2many(
        "plasticos.crm.call.event",
        "partner_id",
        string="CRM Call History",
        help="VanillaSoft calls imported for this ERP person. A call stays on its lead until the contact is bound here.",
    )
    crm_external_table_row_ids = fields.One2many(
        "plasticos.crm.external.table.row",
        "partner_id",
        string="CRM Custom Table Rows",
        help="VanillaSoft custom-table rows imported for this ERP person. "
        "A row stays on its lead until the contact is bound here.",
    )
