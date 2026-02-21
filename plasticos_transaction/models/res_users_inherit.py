from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    default_commission_rate = fields.Float(
        string="Default Commission Rate",
        help="Default commission percentage for this sales rep (0.0-1.0). " "Used when creating new commission rules.",
    )
