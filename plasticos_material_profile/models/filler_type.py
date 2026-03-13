from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosFillerType(models.Model):
    _name = "plasticos.filler.type"
    _description = "Filler Type"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "unique(code)",
        "Filler type code must be unique.",
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
                    raise ValidationError(f"Filler type code '{record.code}' already exists.")
