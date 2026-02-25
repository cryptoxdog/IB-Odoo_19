from odoo import fields, models


class IdempotencyRegistry(models.Model):
    _name = "plasticos.graph.idempotency"
    _description = "Graph Event Idempotency Registry"

    event_id = fields.Char(required=True, index=True)
    processed_at = fields.Datetime(default=fields.Datetime.now)
