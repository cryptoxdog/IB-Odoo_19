from odoo import fields, models


class TierAuditLog(models.Model):
    _name = "plasticos.graph.tier.audit"
    _description = "Tier Evolution Audit Log"

    grade_id = fields.Char(required=True)
    old_tier = fields.Integer()
    new_tier = fields.Integer()
    reason = fields.Char()
