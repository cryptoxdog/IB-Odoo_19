from odoo import fields, models


class PlasticosMaterialColor(models.Model):
    _name = "plasticos.material.color"
    _description = "Material Color Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. natural, white, black).",
    )
    hex_code = fields.Char(
        help="Optional hex color code for UI display (e.g. #FFFFFF).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Material color code must be unique.",
    )
