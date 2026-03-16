from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosMaterialAttribute(models.Model):
    """
    Material attributes for multi-select on products and material profiles.

    These are condition modifiers that can be combined:
    - Clean, Dry, Wet (moisture/cleanliness)
    - Metalized (film with metallic coating - e.g., chip bags)
    - With Metal, No Metal (metal contamination - e.g., rebar in pallets)
    - Printed, No Print (ink/graphics)
    - Dirty, Contaminated (quality issues)
    """

    _name = "plasticos.material.attribute"
    _description = "Material Attribute"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    description = fields.Text()
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _unique_code = models.Constraint(
        "unique(code)",
        "Attribute code must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = vals.get("code")
            if code and self.search([("code", "=", code)], limit=1):
                raise ValidationError(f"Attribute code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code:
            for record in self:
                duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1)
                if duplicate:
                    raise ValidationError(f"Attribute code '{code}' already exists.")
        return super().write(vals)
