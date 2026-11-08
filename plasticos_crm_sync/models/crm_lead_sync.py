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
    vanillasoft_sync_archived = fields.Boolean(
        string="Archived by VanillaSoft Sync",
        default=False,
        copy=False,
        index=True,
        help=(
            "Provenance flag: set when CRM sync archived this lead because VanillaSoft "
            "reported the contact deleted. Only a lead carrying this flag is reactivated "
            "when VanillaSoft later reports the contact active again — a lead an Odoo user "
            "archived for their own reasons never carries it, so sync never reopens it. "
            "Existing rows get the conservative default False on upgrade."
        ),
    )
    crm_call_event_count = fields.Integer(compute="_compute_crm_sync_counts")
    crm_table_row_count = fields.Integer(compute="_compute_crm_sync_counts")

    @api.depends("crm_call_event_ids", "crm_external_table_row_ids")
    def _compute_crm_sync_counts(self):
        for lead in self:
            lead.crm_call_event_count = len(lead.crm_call_event_ids)
            lead.crm_table_row_count = len(lead.crm_external_table_row_ids)
