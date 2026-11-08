from odoo import fields, models


class PlasticosCrmSyncOrphan(models.Model):
    _name = "plasticos.crm.sync.orphan"
    _description = "CRM Sync Orphan Buffer"
    _order = "create_date desc"

    connection_id = fields.Many2one(
        "plasticos.crm.connection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    provider = fields.Char(required=True, index=True)
    kind = fields.Selection(
        [
            ("call", "Call"),
            ("table_row", "Table Row"),
        ],
        required=True,
        index=True,
    )
    contact_external_id = fields.Char(required=True, index=True)
    external_id = fields.Char(index=True)
    payload_json = fields.Json(required=True)
    resolved = fields.Boolean(default=False, index=True)
