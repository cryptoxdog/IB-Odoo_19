from odoo import fields, models


class GraphAnomalyRecord(models.Model):
    _name = "plasticos.graph.anomaly"
    _description = "Graph Anomaly Record"
    _order = "create_date desc"

    tenant_id = fields.Many2one("plasticos.graph.tenant", required=True)
    anomaly_type = fields.Char(required=True)
    entity_id = fields.Char(required=True)
    severity = fields.Float(required=True)
    metadata = fields.Json()
    resolved = fields.Boolean(default=False)
