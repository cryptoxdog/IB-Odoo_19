from odoo import fields, models


class PlasticosMaterialQualityTier(models.Model):
    _name = "plasticos.material.quality.tier"
    _description = "Material Quality Tier"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical UPPER_SNAKE code (GRADE_A, GRADE_B, GRADE_C, REUSABLE, STANDARD).",
    )
    description = fields.Text(
        help="What this quality tier means for a material profile or grade template.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Material quality tier code must be unique.",
    )
