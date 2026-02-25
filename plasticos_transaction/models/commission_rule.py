from odoo import fields, models


class PlasticosCommissionRule(models.Model):
    _name = "plasticos.commission.rule"
    _description = "Commission Rule"

    name = fields.Char(required=True)
    sales_rep_id = fields.Many2one("res.users", required=True, index=True)
    percentage = fields.Float(required=True)
    active = fields.Boolean(default=True)

    # ── Constraints ──────────────────────────────────────────
    _sql_constraints = [
        (
            "unique_sales_rep",
            "unique(sales_rep_id)",
            "Each sales rep may only have one active commission rule.",
        ),
    ]
