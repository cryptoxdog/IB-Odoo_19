from odoo import fields, models


class PlasticosCrmSyncRun(models.Model):
    _name = "plasticos.crm.sync.run"
    _description = "CRM Sync Run Audit"
    _order = "started_at desc, id desc"

    connection_id = fields.Many2one(
        "plasticos.crm.connection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    provider = fields.Selection(
        related="connection_id.provider",
        store=True,
        readonly=True,
    )
    status = fields.Selection(
        [
            ("running", "Running"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("partial", "Partial"),
        ],
        default="running",
        required=True,
        index=True,
    )
    started_at = fields.Datetime(default=fields.Datetime.now, required=True)
    finished_at = fields.Datetime()
    contacts_upserted = fields.Integer(default=0)
    calls_upserted = fields.Integer(default=0)
    table_rows_upserted = fields.Integer(default=0)
    orphans_buffered = fields.Integer(default=0)
    orphans_resolved = fields.Integer(default=0)
    error_excerpt = fields.Text()
