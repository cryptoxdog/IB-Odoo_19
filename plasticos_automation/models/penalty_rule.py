import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class PenaltyRule(models.Model):
    """Penalty rule configuration for automatic penalty calculation.

    Rules are evaluated in sequence order. First matching rule applies.
    Supports weight variance, late delivery, and custom penalty types.
    """

    _name = "plasticos.penalty.rule"
    _description = "Penalty Rule"
    _order = "sequence, id"

    name = fields.Char(string="Rule Name", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    rule_type = fields.Selection(
        [
            ("weight_variance", "Weight Variance"),
            ("late_delivery", "Late Delivery"),
            ("quality_issue", "Quality Issue"),
            ("documentation", "Missing Documentation"),
            ("custom", "Custom"),
        ],
        string="Rule Type",
        required=True,
        default="weight_variance",
    )

    calculation_method = fields.Selection(
        [
            ("percentage", "Percentage of Amount"),
            ("fixed", "Fixed Amount"),
            ("per_unit", "Per Unit/Weight"),
        ],
        string="Calculation Method",
        required=True,
        default="percentage",
    )

    penalty_rate = fields.Float(
        string="Penalty Rate",
        digits="Product Price",
        help="Rate for calculation (percentage, fixed amount, or per-unit rate)",
    )

    min_threshold = fields.Float(
        string="Minimum Threshold",
        help="Minimum variance/days before penalty applies (e.g., 5% variance, 2 days late)",
    )

    max_penalty = fields.Float(
        string="Maximum Penalty",
        digits="Product Price",
        help="Cap on penalty amount (0 = no cap)",
    )

    grace_period_days = fields.Integer(
        string="Grace Period (Days)",
        default=0,
        help="Days before penalty starts accruing",
    )

    product_category_ids = fields.Many2many(
        "product.category",
        "penalty_rule_product_category_rel",
        "rule_id",
        "category_id",
        string="Product Categories",
        help="Leave empty to apply to all categories",
    )

    partner_ids = fields.Many2many(
        "res.partner",
        "penalty_rule_partner_rel",
        "rule_id",
        "partner_id",
        string="Partners",
        help="Leave empty to apply to all partners",
    )

    description = fields.Text(string="Description")

    def toggle_active(self):
        """Toggle active state."""
        for record in self:
            record.active = not record.active

    @api.model
    def calculate_penalty(self, invoice, variance_percent=0.0, days_late=0):
        """Calculate penalty for an invoice based on applicable rules.

        Args:
            invoice: account.move record
            variance_percent: Weight variance percentage (for weight_variance rules)
            days_late: Days past due (for late_delivery rules)

        Returns:
            dict: {amount: float, reason: str, rule_id: int} or empty dict
        """
        partner = invoice.partner_id
        product_categories = invoice.invoice_line_ids.mapped("product_id.categ_id")

        rules = self.search([("active", "=", True)], order="sequence, id")

        for rule in rules:
            if not rule._is_applicable(partner, product_categories):
                continue

            penalty_amount = 0.0
            reason = ""

            if rule.rule_type == "weight_variance" and variance_percent > 0:
                if variance_percent >= rule.min_threshold:
                    penalty_amount = rule._compute_amount(invoice, variance_percent)
                    reason = f"Weight variance {variance_percent:.1f}% exceeds threshold {rule.min_threshold:.1f}%"

            elif rule.rule_type == "late_delivery" and days_late > 0:
                effective_days = max(0, days_late - rule.grace_period_days)
                if effective_days >= rule.min_threshold:
                    penalty_amount = rule._compute_amount(invoice, effective_days)
                    reason = f"Delivery {days_late} days late (grace: {rule.grace_period_days} days)"

            if penalty_amount > 0:
                if rule.max_penalty > 0:
                    penalty_amount = min(penalty_amount, rule.max_penalty)
                return {
                    "amount": penalty_amount,
                    "reason": reason,
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                }

        return {}

    def _is_applicable(self, partner, product_categories):
        """Check if rule applies to given partner and product categories."""
        self.ensure_one()

        if self.partner_ids and partner.id not in self.partner_ids.ids:
            return False

        if self.product_category_ids:
            if not any(cat.id in self.product_category_ids.ids for cat in product_categories):
                return False

        return True

    def _compute_amount(self, invoice, value):
        """Compute penalty amount based on calculation method.

        Args:
            invoice: account.move record
            value: variance_percent or days_late depending on rule_type
        """
        self.ensure_one()

        if self.calculation_method == "percentage":
            return invoice.amount_total * (self.penalty_rate / 100)
        elif self.calculation_method == "fixed":
            return self.penalty_rate
        elif self.calculation_method == "per_unit":
            return self.penalty_rate * value
        return 0.0
