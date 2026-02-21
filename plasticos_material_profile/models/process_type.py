from odoo import fields, models


class PlasticosProcessType(models.Model):
    _name = "plasticos.process.type"
    _description = "Process Type Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. injection, extrusion).",
    )
    description = fields.Text(
        help="Detailed description of this manufacturing process.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _check_unique_code = models.Constraint(
        "unique(code)",
        "Process type code must be unique.",
    )
