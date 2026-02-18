from odoo import models, fields


class PlasticosCommissionRule(models.Model):
    _name = "plasticos.commission.rule"
    _description = "Commission Rule"

    name = fields.Char(required=True)
    sales_rep_id = fields.Many2one("res.users", required=True, index=True)
    percentage = fields.Float(required=True)
    active = fields.Boolean(default=True)

    # ── Constraints (Odoo 19 models.Constraint) ──────────────
    _check_unique_rep = models.Constraint(
        "unique(sales_rep_id)",
        "Each sales rep may only have one active commission rule.",
    )
