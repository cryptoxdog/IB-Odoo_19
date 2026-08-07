from odoo import api, fields, models


class CrmLeadSync(models.Model):
    _inherit = "crm.lead"

    crm_call_event_ids = fields.One2many(
        "plasticos.crm.call.event",
        "lead_id",
        string="CRM Call Events",
    )
    crm_external_table_row_ids = fields.One2many(
        "plasticos.crm.external.table.row",
        "lead_id",
        string="CRM Custom Table Rows",
    )
    crm_call_event_count = fields.Integer(compute="_compute_crm_sync_counts")
    crm_table_row_count = fields.Integer(compute="_compute_crm_sync_counts")

    @api.depends("crm_call_event_ids", "crm_external_table_row_ids")
    def _compute_crm_sync_counts(self):
        for lead in self:
            lead.crm_call_event_count = len(lead.crm_call_event_ids)
            lead.crm_table_row_count = len(lead.crm_external_table_row_ids)
