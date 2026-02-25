from odoo import fields, models


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

    # Link to boolean field behavior
    boolean_field = fields.Char(
        help="Name of the boolean field this attribute maps to (e.g., 'has_metal').",
    )
    boolean_value = fields.Boolean(
        help="Value to set when this attribute is selected.",
    )

    _sql_constraints = [
        (
            "unique_code",
            "unique(code)",
            "Attribute code must be unique.",
        ),
    ]
