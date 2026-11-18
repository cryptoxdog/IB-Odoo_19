from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosCapabilityType(models.Model):
    """What a line does. People may add types; the seed list is the canonical start."""

    _name = "plasticos.capability.type"
    _description = "Capability Type"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Stable key for this type, for example shredding.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    details_definition = fields.PropertiesDefinition(
        string="Detail fields",
        help="Detail fields a row of this type shows. An upgrade keeps fields an operations manager added.",
    )

    _code_unique = models.Constraint(
        "unique(code)",
        "Capability type code must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Capability type code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code and self and (len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1)):
            raise ValidationError(f"Capability type code '{code}' already exists.")
        return super().write(vals)
