from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosPolymer(models.Model):
    _name = "plasticos.polymer"
    _description = "Polymer Type Master"
    _order = "sequence, name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(
        required=True,
        index=True,
        help="Canonical lowercase code used across all modules (e.g. hdpe, pp).",
    )
    full_name = fields.Char(
        help="Full chemical / trade name (e.g. High-Density Polyethylene).",
    )
    resin_id_code = fields.Char(
        help="SPI resin identification code (1-7) where applicable.",
    )
    category = fields.Selection(
        [
            ("commodity", "Commodity"),
            ("engineering", "Engineering"),
            ("specialty", "Specialty"),
        ],
        default="commodity",
        index=True,
    )
    description = fields.Text(
        help="Additional description or notes about this polymer type.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    _unique_code = models.Constraint(
        "unique(code)",
        "Polymer code must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        codes = [vals["code"] for vals in vals_list if vals.get("code")]
        taken = set(self.search([("code", "in", codes)]).mapped("code")) if codes else set()
        for code in codes:
            if code in taken:
                raise ValidationError(f"Polymer code '{code}' already exists.")
        return super().create(vals_list)

    def _purchase_product(self):
        """Purchase product for this polymer. The product addon supplies it."""
        self.ensure_one()
        return False

    def write(self, vals):
        code = vals.get("code")
        if code and self:
            # One code written to several records is always a duplicate; otherwise one
            # query asks whether a record outside this recordset already holds it.
            if len(self) > 1 or self.search([("code", "=", code), ("id", "not in", self.ids)], limit=1):
                raise ValidationError(f"Polymer code '{code}' already exists.")
        return super().write(vals)
