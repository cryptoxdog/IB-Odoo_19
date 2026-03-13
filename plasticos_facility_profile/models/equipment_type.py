from odoo import api, fields, models
from odoo.exceptions import ValidationError


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

    # ── Constraints ──────────────────────────────────────────
    _unique_code = models.Constraint(
        "unique(code)",
        "Equipment type code must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            code = vals.get("code")
            if code and self.search([("code", "=", code)], limit=1):
                raise ValidationError(f"Equipment type code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code:
            for record in self:
                duplicate = self.search([("code", "=", code), ("id", "!=", record.id)], limit=1)
                if duplicate:
                    raise ValidationError(f"Equipment type code '{code}' already exists.")
        return super().write(vals)
