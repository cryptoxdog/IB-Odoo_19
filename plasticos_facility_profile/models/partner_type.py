from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosPartnerType(models.Model):
    """Canonical partner/facility type master registry."""

    _name = "plasticos.partner.type"
    _description = "Partner Type Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code (e.g. processor, broker, mrf).",
    )
    description = fields.Text(
        help="Detailed description of this partner type.",
    )
    is_facility = fields.Boolean(
        default=True,
        help="True if this type applies to facilities (companies with parent).",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Partner type code must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = vals.get("code")
            if code and self.search([("code", "=", code)], limit=1):
                raise ValidationError(f"Partner type code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code:
            for record in self:
                duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1)
                if duplicate:
                    raise ValidationError(f"Partner type code '{code}' already exists.")
        return super().write(vals)
