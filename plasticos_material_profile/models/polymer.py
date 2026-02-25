from odoo import fields, models


class PlasticosPolymer(models.Model):
    _name = "plasticos.polymer"
    _description = "Polymer Type Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code used across all modules (e.g. hdpe, pp).",
    )
    full_name = fields.Char(
        help="Full chemical / trade name (e.g. High-Density Polyethylene).",
    )
    resin_id_code = fields.Char(
        help="SPI resin identification code (1-7) where applicable.",
    )
    category = fields.Selection(
        [
            ("commodity", "Commodity"),
            ("engineering", "Engineering"),
            ("specialty", "Specialty"),
        ],
        default="commodity",
        index=True,
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _check_unique_code = models.Constraint(
        "unique(code)",
        "Polymer code must be unique.",
    )
