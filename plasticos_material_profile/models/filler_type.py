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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = vals.get("code")
            if code and self.search([("code", "=", code)], limit=1):
                raise ValidationError(f"Filler type code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code:
            for record in self:
                duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1)
                if duplicate:
                    raise ValidationError(f"Filler type code '{code}' already exists.")
        return super().write(vals)
