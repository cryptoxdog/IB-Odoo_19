from odoo import fields, models


class EmergentCluster(models.Model):
    _name = "plasticos.graph.emergent.cluster"
    _description = "Emergent Grade Cluster"
    _order = "density_score desc"

    cluster_id = fields.Char(required=True, index=True)
    size = fields.Integer(required=True)
    density_score = fields.Float(required=True)
    modularity = fields.Float(required=True)
    status = fields.Selection(
        [
            ("detected", "Detected"),
            ("validated", "Validated"),
            ("rejected", "Rejected"),
            ("materialized", "Materialized"),
        ],
        default="detected",
    )

    grade_ids = fields.Json(required=True)
