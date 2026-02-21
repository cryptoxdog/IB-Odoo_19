from odoo import models, fields


class PlasticosMaterialForm(models.Model):
    _name = "plasticos.material.form"
    _description = "Material Form Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. bale, regrind, pellet).",
    )
    description = fields.Text(
        help="Detailed description of this material form.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _check_unique_code = models.Constraint(
        "unique(code)",
        "Material form code must be unique.",
    )
