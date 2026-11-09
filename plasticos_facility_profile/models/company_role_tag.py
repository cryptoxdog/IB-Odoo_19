from odoo import fields, models


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
