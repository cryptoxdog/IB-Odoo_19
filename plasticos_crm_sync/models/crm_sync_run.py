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
    # Scope — what this run asked the provider for. Without it a rolling
    # incremental pass and the operator's full import are indistinguishable in
    # the ledger, and a ≤30-day `success` reads like a historical census.
    kind = fields.Selection(
        [
            ("incremental", "Incremental (rolling window)"),
            ("full_import", "Full import (operator floors)"),
        ],
        index=True,
        help="Incremental: the cron/manual pass over the provider's rolling window. "
        "Full import: the one-shot bootstrap from operator-supplied historical floors. "
        "Empty on runs recorded before scope tracking existed.",
    )
    contact_scope_from_utc = fields.Char(
        string="Contacts Requested From (UTC)",
        help="The modified_after bound actually sent to the Contacts endpoint, after any clamp "
        "to the provider lookback. A clamp is reported in the error excerpt and makes the run partial.",
    )
    call_scope_from_utc = fields.Char(
        string="Calls Requested From (UTC)",
        help="Start of the call-history window this run asked for.",
    )
    call_scope_to_utc = fields.Char(
        string="Calls Requested To (UTC)",
        help="End of the call-history window this run asked for. A full import fills this when its "
        "catch-up phase closes the window; it stays empty when the import did not get that far.",
    )
    started_at = fields.Datetime(default=fields.Datetime.now, required=True)
    finished_at = fields.Datetime()
    contacts_seen = fields.Integer(default=0)
    contacts_upserted = fields.Integer(default=0)
    contacts_created = fields.Integer(default=0)
    contacts_updated = fields.Integer(default=0)
    contacts_unchanged = fields.Integer(default=0)
    contacts_duplicate_rejected = fields.Integer(default=0)
    contacts_failed = fields.Integer(default=0)
    calls_seen = fields.Integer(default=0)
    calls_upserted = fields.Integer(default=0)
    calls_created = fields.Integer(default=0)
    calls_updated = fields.Integer(default=0)
    calls_unchanged = fields.Integer(default=0)
    calls_failed = fields.Integer(default=0)
    table_rows_upserted = fields.Integer(default=0)
    orphans_buffered = fields.Integer(default=0)
    orphans_resolved = fields.Integer(default=0)
    error_excerpt = fields.Text()
