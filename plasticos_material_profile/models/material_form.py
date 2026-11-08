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

    @api.model_create_multi
    def create(self, vals_list):
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Material form code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code and self:
            # One code written to several records is always a duplicate; otherwise one
            # query asks whether a record outside this recordset already holds it.
            if len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Material form code '{code}' already exists.")
        return super().write(vals)
