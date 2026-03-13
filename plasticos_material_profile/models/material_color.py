from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    @api.constrains("code")
    def _check_code_unique(self):
        for record in self:
            if record.code:
                duplicate = self.search(
                    [
                        ("code", "=", record.code),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(f"Material color code '{record.code}' already exists.")
