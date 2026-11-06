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
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Equipment type code '{code}' already exists.")
        return super().create(vals_list)

    def write(self, vals):
        code = vals.get("code")
        if code and self:
            # One code written to several records is always a duplicate; otherwise one
            # query asks whether a record outside this recordset already holds it.
            if len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Equipment type code '{code}' already exists.")
        return super().write(vals)
