from odoo import fields, models


class PlasticosMaterialGrade(models.Model):
    _name = "plasticos.material.grade"
    _description = "Material Grade Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical UPPER_SNAKE code (e.g. DRUMS, IBC_TOTES, OCC).",
    )
    description = fields.Text(
        help="What items of this grade are (drums, totes, pallets) before processing.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Material grade code must be unique.",
    )
