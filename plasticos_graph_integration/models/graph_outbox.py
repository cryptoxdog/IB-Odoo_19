from odoo import fields, models


class GraphOutbox(models.Model):
    _name = "plasticos.graph.outbox"
    _description = "Graph Outbox (Idempotent Sync Queue)"
    _order = "create_date asc"

    model_name = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)
    event_type = fields.Selection([("upsert", "Upsert"), ("delete", "Delete")], required=True)

    status = fields.Selection(
        [("pending", "Pending"), ("processed", "Processed"), ("failed", "Failed")], default="pending", index=True
    )

    error_message = fields.Text()

    def mark_processed(self):
        self.write({"status": "processed"})

    def mark_failed(self, error):
        self.write({"status": "failed", "error_message": str(error)})
