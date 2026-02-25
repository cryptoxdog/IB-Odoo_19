from odoo import fields, models


class ExplainabilityRecord(models.Model):
    _name = "plasticos.explainability.record"
    _description = "Graph Explainability Record"
    _order = "create_date desc"

    intake_id = fields.Many2one(
        "plasticos.intake",
        required=True,
        index=True,
    )

    facility_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
    )

    grade_id = fields.Char(required=True)

    scoring_breakdown = fields.Json(
        required=True,
        help="Structured scoring components (structural, similarity, reinforcement, confidence)",
    )

    path_trace = fields.Json(
        required=True,
        help="Graph traversal path explanation",
    )
