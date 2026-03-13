from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosMaterialForm(models.Model):
    _name = "plasticos.material.form"
    _description = "Material Form Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. bales, regrind, pellet).",
    )
    description = fields.Text(
        help="Detailed description of this material form.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Material form code must be unique.",
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
                    raise ValidationError(f"Material form code '{record.code}' already exists.")
