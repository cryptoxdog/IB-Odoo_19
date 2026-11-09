from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosCompanyRoleTag(models.Model):
    """One trade role a company can carry. A partner may carry several."""

    _name = "plasticos.company.role.tag"
    _description = "Company Role Tag"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    description = fields.Char()
    sequence = fields.Integer(default=10)
    color = fields.Integer()
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "unique(code)",
        "Company role tag code must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Company role tag code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code and self:
            # One code written to several records is always a duplicate; otherwise one
            # query asks whether a record outside this recordset already holds it.
            if len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Company role tag code '{code}' already exists.")
        return super().write(vals)
