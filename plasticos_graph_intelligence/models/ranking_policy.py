from odoo import fields, models


class RankingPolicy(models.Model):
    _name = "plasticos.ranking.policy"
    _description = "Deterministic Ranking Policy"
    _order = "version desc"

    name = fields.Char(required=True)
    version = fields.Integer(required=True, index=True)
    structural_weight = fields.Float(required=True)
    similarity_weight = fields.Float(required=True)
    reinforcement_weight = fields.Float(required=True)
    confidence_weight = fields.Float(required=True)
    strict_similarity_threshold = fields.Float(required=True)

    is_frozen = fields.Boolean(default=False)
    frozen_at = fields.Datetime()

    def freeze(self):
        self.write(
            {
                "is_frozen": True,
                "frozen_at": fields.Datetime.now(),
            }
        )
