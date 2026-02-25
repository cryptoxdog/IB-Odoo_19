from odoo import fields, models


class PlasticosSourceType(models.Model):
    _name = "plasticos.source.type"
    _description = "Material Source Type Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. post_industrial, post_consumer).",
    )
    description = fields.Text(
        help="Detailed description of this source type.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Source type code must be unique.",
    )
