from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosPackagingType(models.Model):
    """
    Packaging types for how material is shipped/stored.

    Distinct from Form (what the material IS) - this is how it's packaged.
    Examples: Gaylords, Super Sacks, Bales, Loose, Palletized
    """

    _name = "plasticos.packaging.type"
    _description = "Packaging Type"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "unique(code)",
        "Packaging type code must be unique.",
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
                    raise ValidationError(f"Packaging type code '{record.code}' already exists.")
