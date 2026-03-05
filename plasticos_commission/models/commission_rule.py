from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosCommissionRule(models.Model):
    _name = "plasticos.commission.rule"
    _description = "Commission Rule"

    name = fields.Char(required=True)
    sales_rep_id = fields.Many2one("res.users", string="Sales Rep", required=True)
    percentage = fields.Float(
        string="Commission Rate",
        required=True,
        digits=(5, 4),
        help="Commission as decimal fraction (e.g., 0.05 = 5%)",
    )
    display_percentage = fields.Float(
        string="Commission %",
        compute="_compute_display_percentage",
        inverse="_inverse_display_percentage",
        help="Commission as percentage for display (e.g., 5.0 = 5%)",
    )
    active = fields.Boolean(default=True)

    @api.depends("percentage")
    def _compute_display_percentage(self):
        for rec in self:
            rec.display_percentage = (rec.percentage or 0.0) * 100

    def _inverse_display_percentage(self):
        for rec in self:
            rec.percentage = (rec.display_percentage or 0.0) / 100

    @api.constrains("percentage")
    def _check_percentage_range(self):
        """Validate commission rate is a valid fraction 0.0–1.0."""
        for rec in self:
            if rec.percentage < 0.0 or rec.percentage > 1.0:
                raise ValidationError(
                    f"Commission rate must be between 0.0 and 1.0 (got {rec.percentage}). "
                    f"Use decimal fraction, e.g., 0.05 for 5%."
                )
