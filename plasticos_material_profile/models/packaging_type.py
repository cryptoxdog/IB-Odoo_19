from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosPackagingType(models.Model):
    """
    Packaging types for how material is shipped/stored.

    Distinct from Form (what the material IS) - this is how it's packaged.
    Examples: Gaylords, Supersacs, Bales, Loose, Palletized
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

    @api.model_create_multi
    def create(self, vals_list):
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Packaging type code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code and self:
            # One code written to several records is always a duplicate; otherwise one
            # query asks whether a record outside this recordset already holds it.
            if len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Packaging type code '{code}' already exists.")
        return super().write(vals)
