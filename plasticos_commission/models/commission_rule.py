from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlasticosCommissionRule(models.Model):
    """Commission rule with tiered rates, validity periods, and applicability filters.

    Supports multiple calculation types:
    - percentage: Simple percentage of gross margin
    - fixed: Fixed amount per transaction
    - tiered: Different rates based on amount ranges
    """

    _name = "plasticos.commission.rule"
    _description = "Commission Rule"
    _order = "sequence, id"

    name = fields.Char(required=True, default="New Commission Rule")
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(default=True)

    # ── Sales Rep Assignment ──────────────────────────────────
    sales_rep_id = fields.Many2one("res.users", string="Sales Rep", required=True, ondelete="restrict")

    # Active rows only. Inactive rules for the same representative stay legal.
    _unique_active_sales_rep = models.UniqueIndex(
        "(sales_rep_id) WHERE (active IS TRUE)",
        "A sales representative may have only one active commission rule.",
    )

    # ── Calculation Type ──────────────────────────────────────
    calculation_type = fields.Selection(
        [
            ("percentage", "Percentage of Margin"),
            ("fixed", "Fixed Amount"),
            ("tiered", "Tiered Rates"),
        ],
        string="Calculation Type",
        required=True,
        default="percentage",
    )

    # ── Rate Fields ───────────────────────────────────────────
    percentage = fields.Float(
        string="Commission Rate",
        required=True,
        default=0.05,
        digits=(5, 4),
        help="Commission as decimal fraction (e.g., 0.05 = 5%)",
    )
    display_percentage = fields.Float(
        string="Commission %",
        compute="_compute_display_percentage",
        inverse="_inverse_display_percentage",
        help="Commission as percentage for display (e.g., 5.0 = 5%)",
    )
    fixed_amount = fields.Float(
        string="Fixed Amount",
        digits="Product Price",
        help="Fixed commission amount (for fixed calculation type)",
    )

    # ── Validity Period ───────────────────────────────────────
    date_from = fields.Date(string="Valid From")
    date_to = fields.Date(string="Valid To")

    # ── Amount Conditions ─────────────────────────────────────
    min_amount = fields.Float(
        string="Minimum Amount",
        digits="Product Price",
        help="Minimum transaction amount for this rule to apply",
    )
    max_amount = fields.Float(
        string="Maximum Amount",
        digits="Product Price",
        help="Maximum transaction amount for this rule to apply (0 = no limit)",
    )

    # ── Applicability Filters ─────────────────────────────────
    product_category_ids = fields.Many2many(
        "product.category",
        "commission_rule_product_category_rel",
        "rule_id",
        "category_id",
        string="Product Categories",
        help="Leave empty to apply to all categories",
    )
    product_ids = fields.Many2many(
        "product.product",
        "commission_rule_product_rel",
        "rule_id",
        "product_id",
        string="Products",
        help="Leave empty to apply to all products",
    )
    partner_ids = fields.Many2many(
        "res.partner",
        "commission_rule_partner_rel",
        "rule_id",
        "partner_id",
        string="Partners",
        help="Leave empty to apply to all partners",
    )

    # ── Tiered Rates ──────────────────────────────────────────
    tier_ids = fields.One2many(
        "plasticos.commission.tier",
        "rule_id",
        string="Tiered Rates",
    )

    # ── Computed Methods ──────────────────────────────────────
    @api.depends("percentage")
    def _compute_display_percentage(self):
        for rec in self:
            rec.display_percentage = (rec.percentage or 0.0) * 100

    def _inverse_display_percentage(self):
        for rec in self:
            rec.percentage = (rec.display_percentage or 0.0) / 100

    def _reject_active_sales_rep_conflicts(self, rep_ids, exclude_ids):
        """Friendly check for the intended active representatives.

        The partial unique index is the concurrency authority. This method
        only raises before the write so the operator sees the business error.
        """
        if not rep_ids:
            return
        seen = set()
        conflict_ids = set()
        for rep_id in rep_ids:
            if rep_id in seen:
                conflict_ids.add(rep_id)
            seen.add(rep_id)
        domain = [("sales_rep_id", "in", list(seen)), ("active", "=", True)]
        if exclude_ids:
            domain.append(("id", "not in", list(exclude_ids)))
        conflict_ids.update(self.search(domain).mapped("sales_rep_id").ids)
        if not conflict_ids:
            return
        rep = self.env["res.users"].browse(sorted(conflict_ids)[:1])
        raise ValidationError(f"Sales rep {rep.name} already has an active commission rule.")

    @api.model_create_multi
    def create(self, vals_list):
        active_reps = [
            vals["sales_rep_id"] for vals in vals_list if vals.get("sales_rep_id") and vals.get("active", True)
        ]
        self._reject_active_sales_rep_conflicts(active_reps, exclude_ids=())
        return super().create(vals_list)

    def write(self, vals):
        if "sales_rep_id" in vals or "active" in vals:
            rep_ids = []
            for rec in self:
                rep_id = vals.get("sales_rep_id", rec.sales_rep_id.id)
                is_active = vals.get("active", rec.active)
                if rep_id and is_active:
                    rep_ids.append(rep_id)
            self._reject_active_sales_rep_conflicts(rep_ids, exclude_ids=self.ids)
        return super().write(vals)

    # ── Constraints ───────────────────────────────────────────
    @api.constrains("name")
    def _check_name_required(self):
        """Ensure name is not empty or falsy."""
        for rec in self:
            if not rec.name:
                raise ValidationError("Commission rule name is required.")

    @api.constrains("sales_rep_id")
    def _check_sales_rep_required(self):
        """Ensure sales_rep_id is set."""
        for rec in self:
            if not rec.sales_rep_id:
                raise ValidationError("Sales representative is required.")

    @api.constrains("percentage")
    def _check_percentage_range(self):
        """Validate commission rate is a valid fraction 0.0–1.0."""
        for rec in self:
            if rec.percentage < 0.0 or rec.percentage > 1.0:
                raise ValidationError(
                    f"Commission rate must be between 0.0 and 1.0 (got {rec.percentage}). "
                    f"Use decimal fraction, e.g., 0.05 for 5%."
                )

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        """Ensure date_from <= date_to if both are set."""
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError("Valid From date must be before Valid To date.")

    @api.constrains("min_amount", "max_amount")
    def _check_amount_range(self):
        """Ensure min_amount <= max_amount if both are set."""
        for rec in self:
            if rec.min_amount and rec.max_amount and rec.min_amount > rec.max_amount:
                raise ValidationError("Minimum amount must be less than maximum amount.")

    # ── Actions ───────────────────────────────────────────────
    def toggle_active(self):
        """Toggle active state."""
        for record in self:
            record.active = not record.active

    # ── Commission Calculation ────────────────────────────────
    def calculate_commission(self, gross_margin, transaction_amount=0.0):
        """Calculate commission based on rule type.

        Args:
            gross_margin: The gross margin to calculate commission from
            transaction_amount: Total transaction amount (for tiered calculation)

        Returns:
            float: Commission amount
        """
        self.ensure_one()

        if self.calculation_type == "percentage":
            return gross_margin * self.percentage

        elif self.calculation_type == "fixed":
            return self.fixed_amount or 0.0

        elif self.calculation_type == "tiered":
            return self._calculate_tiered_commission(gross_margin, transaction_amount)

        return 0.0

    def _calculate_tiered_commission(self, gross_margin, transaction_amount):
        """Calculate commission using tiered rates."""
        self.ensure_one()

        if not self.tier_ids:
            return gross_margin * self.percentage

        for tier in self.tier_ids.sorted("min_amount"):
            if tier.min_amount <= transaction_amount:
                if not tier.max_amount or transaction_amount <= tier.max_amount:
                    return gross_margin * tier.rate

        return gross_margin * self.percentage

    def is_applicable(self, transaction_date=None, transaction_amount=0.0, product=None, partner=None):
        """Check if this rule is applicable for given criteria.

        Args:
            transaction_date: Date to check validity
            transaction_amount: Amount to check against min/max
            product: Product record to check category/product filters
            partner: Partner record to check partner filters

        Returns:
            bool: True if rule is applicable
        """
        self.ensure_one()

        if transaction_date:
            if self.date_from and transaction_date < self.date_from:
                return False
            if self.date_to and transaction_date > self.date_to:
                return False

        if self.min_amount and transaction_amount < self.min_amount:
            return False
        if self.max_amount and transaction_amount > self.max_amount:
            return False

        if product:
            if self.product_ids and product.id not in self.product_ids.ids:
                return False
            if self.product_category_ids and product.categ_id.id not in self.product_category_ids.ids:
                return False

        if partner and self.partner_ids and partner.id not in self.partner_ids.ids:
            return False

        return True


class PlasticosCommissionTier(models.Model):
    """Commission tier for tiered rate calculation."""

    _name = "plasticos.commission.tier"
    _description = "Commission Tier"
    _order = "min_amount"

    rule_id = fields.Many2one(
        "plasticos.commission.rule",
        string="Commission Rule",
        required=True,
        ondelete="cascade",
    )

    min_amount = fields.Float(
        string="Minimum Amount",
        digits="Product Price",
        required=True,
        help="Minimum transaction amount for this tier",
    )
    max_amount = fields.Float(
        string="Maximum Amount",
        digits="Product Price",
        help="Maximum transaction amount for this tier (0 = no limit)",
    )
    rate = fields.Float(
        string="Rate",
        digits=(5, 4),
        required=True,
        help="Commission rate as decimal fraction (e.g., 0.05 = 5%)",
    )
    display_rate = fields.Float(
        string="Rate %",
        compute="_compute_display_rate",
        inverse="_inverse_display_rate",
    )

    @api.depends("rate")
    def _compute_display_rate(self):
        for rec in self:
            rec.display_rate = (rec.rate or 0.0) * 100

    def _inverse_display_rate(self):
        for rec in self:
            rec.rate = (rec.display_rate or 0.0) / 100

    @api.constrains("rate")
    def _check_rate_range(self):
        """Validate tier rate is a valid fraction 0.0–1.0."""
        for rec in self:
            if rec.rate < 0.0 or rec.rate > 1.0:
                raise ValidationError(f"Tier rate must be between 0.0 and 1.0 (got {rec.rate}).")

    @api.constrains("min_amount", "max_amount")
    def _check_amount_range(self):
        """Ensure min_amount <= max_amount if both are set."""
        for rec in self:
            if rec.max_amount and rec.min_amount > rec.max_amount:
                raise ValidationError("Minimum amount must be less than maximum amount.")
