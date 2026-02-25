from odoo import fields, models


class ExpansionInsight(models.Model):
    _name = "plasticos.expansion.insight"
    _description = "Grade Expansion Opportunity"
    _order = "opportunity_score desc"

    facility_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
    )

    candidate_grade_id = fields.Char(required=True, index=True)

    similarity_score = fields.Float(required=True)
    opportunity_score = fields.Float(required=True)

    recommended_action = fields.Selection(
        [
            ("engage_sales", "Engage Sales"),
            ("monitor", "Monitor"),
            ("low_priority", "Low Priority"),
        ],
        default="monitor",
    )
