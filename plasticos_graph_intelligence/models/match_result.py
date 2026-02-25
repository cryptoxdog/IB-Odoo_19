from odoo import fields, models


class MatchResult(models.Model):
    _name = "plasticos.match.result"
    _description = "Graph Match Result"
    _order = "final_score desc"

    match_request_id = fields.Many2one(
        "plasticos.match.request",
        required=True,
        ondelete="cascade",
        index=True,
    )

    facility_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
    )

    grade_id = fields.Char(required=True, index=True)

    structural_score = fields.Float(required=True)
    similarity_score = fields.Float(default=0.0)
    reinforcement_score = fields.Float(default=0.0)
    confidence_score = fields.Float(default=0.0)

    final_score = fields.Float(required=True, index=True)

    explainability_id = fields.Many2one(
        "plasticos.explainability.record",
        ondelete="set null",
    )
