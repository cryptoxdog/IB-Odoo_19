from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosCommissionRule(models.Model):
    _name = "plasticos.commission.rule"
    _description = "Commission Rule"

    name = fields.Char(required=True)
    sales_rep_id = fields.Many2one("res.users", required=True, index=True)
    percentage = fields.Float(
        required=True,
        help="Commission rate as a fraction (0.0–1.0). Example: 0.15 = 15%.",
    )
    active = fields.Boolean(default=True)

    @api.constrains("percentage")
    def _check_percentage_range(self):
        for rec in self:
            if not (0.0 <= rec.percentage <= 1.0):
                raise ValidationError("Commission percentage must be between 0.0 and 1.0 (e.g., 0.15 for 15%).")

    @api.constrains("sales_rep_id", "active")
    def _check_unique_active_sales_rep(self):
        """Ensure only one active commission rule per sales rep.

        NOTE: This is a Python constraint, not SQL, because SQL unique constraints
        don't respect Odoo's active field filtering. A SQL constraint would block
        creating a new rule even if the old one is archived.
        """
        for rec in self:
            if not rec.active:
                continue
            duplicate = self.search(
                [
                    ("sales_rep_id", "=", rec.sales_rep_id.id),
                    ("active", "=", True),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(f"Sales rep {rec.sales_rep_id.name} already has an active commission rule.")
