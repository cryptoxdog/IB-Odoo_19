from odoo import fields, models


class PlasticosCommissionRule(models.Model):
    _name = "plasticos.commission.rule"
    _description = "Commission Rule"

    name = fields.Char(required=True)
    sales_rep_id = fields.Many2one("res.users", required=True)
    percentage = fields.Float(required=True)
    active = fields.Boolean(default=True)
