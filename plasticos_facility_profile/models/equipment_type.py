from odoo import fields, models


class PlasticosEquipmentType(models.Model):
    _name = "plasticos.equipment.type"
    _description = "Equipment Type Master"
    _order = "category, sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(
        required=True,
        help="Machine-readable key, e.g. 'horizontal_baler'.",
    )
    category = fields.Selection(
        [
            ("equipment", "Equipment"),
            ("handling", "Material Handling"),
            ("quality", "Quality Processing"),
        ],
        required=True,
        default="equipment",
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Constraints (Odoo 19 models.Constraint) ──────────────
    _check_unique_code = models.Constraint(
        "unique(code)",
        "Equipment type code must be unique.",
    )
