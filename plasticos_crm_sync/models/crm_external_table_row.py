from odoo import fields, models

RES_PARTNER = "res.partner"


class PlasticosCrmExternalTableRow(models.Model):
    _name = "plasticos.crm.external.table.row"
    _description = "CRM External Custom Table Row"
    _order = "table_name, id desc"

    provider = fields.Char(required=True, index=True)
    lead_id = fields.Many2one(
        "crm.lead",
        string="Lead",
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        RES_PARTNER,
        string="Contact",
        domain=[("is_company", "=", False)],
        ondelete="set null",
        index=True,
        help="ERP person this custom-table row belongs to. Set when the VanillaSoft contact is bound to that person.",
    )
    contact_external_id = fields.Char(index=True)
    table_id = fields.Char(required=True, index=True)
    table_name = fields.Char()
    external_row_id = fields.Char(required=True, index=True)
    fields_json = fields.Json(string="Fields")

    _unique_provider_table_row = models.Constraint(
        "unique(provider, table_id, external_row_id)",
        "Custom table row already imported for this provider.",
    )
