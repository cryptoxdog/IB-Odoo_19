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
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Attribute code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code and self:
            # One code written to several records is always a duplicate; otherwise one
            # query asks whether a record outside this recordset already holds it.
            if len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Attribute code '{code}' already exists.")
        return super().write(vals)
