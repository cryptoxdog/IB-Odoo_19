import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountMovePenalty(models.Model):
    """Invoice/Bill extension for penalty and scrap management.

    Adds penalty tracking, weight variance approval, freight reconciliation,
    and commission tracking to account.move.
    """

    _inherit = "account.move"

    # ── Transaction Link ──────────────────────────────────────
    transaction_id = fields.Many2one(
        "plasticos.transaction",
        string="Transaction",
        index=True,
        help="Linked transaction for scrap management",
    )

    reconciliation_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("reconciled", "Reconciled"),
            ("disputed", "Disputed"),
        ],
        string="Reconciliation Status",
        default="pending",
    )

    # ── Penalty Fields ────────────────────────────────────────
    has_penalty = fields.Boolean(
        string="Has Penalty",
        default=False,
        tracking=True,
    )
    penalty_amount = fields.Float(
        string="Penalty Amount",
        digits="Product Price",
        tracking=True,
    )
    penalty_reason = fields.Text(string="Penalty Reason")
    penalty_rule_id = fields.Many2one(
        "plasticos.penalty.rule",
        string="Applied Penalty Rule",
    )

    # ── Weight Variance ───────────────────────────────────────
    weight_variance_percent = fields.Float(
        string="Weight Variance (%)",
        digits=(5, 2),
        help="Percentage variance between expected and actual weight",
    )
    weight_variance_approved = fields.Boolean(
        string="Variance Approved",
        default=False,
        tracking=True,
    )
    weight_variance_approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
    )
    weight_variance_approved_date = fields.Datetime(string="Approval Date")

    # ── Commission ────────────────────────────────────────────
    commission_amount = fields.Float(
        string="Commission Amount",
        digits="Product Price",
        compute="_compute_commission_amount",
        store=True,
    )
    commission_paid = fields.Boolean(
        string="Commission Paid",
        default=False,
        tracking=True,
    )

    # ── Freight ───────────────────────────────────────────────
    freight_charged = fields.Float(
        string="Freight Charged",
        digits="Product Price",
        help="Freight amount charged to customer",
    )
    freight_actual = fields.Float(
        string="Freight Actual",
        digits="Product Price",
        help="Actual freight cost incurred",
    )
    freight_variance = fields.Float(
        string="Freight Variance",
        digits="Product Price",
        compute="_compute_freight_variance",
        store=True,
    )

    reconciliation_notes = fields.Text(string="Reconciliation Notes")

    # ── Adjustment Lines ──────────────────────────────────────
    adjustment_line_ids = fields.One2many(
        "plasticos.invoice.adjustment",
        "move_id",
        string="Adjustments",
    )

    # ── Computed Methods ──────────────────────────────────────
    @api.depends("transaction_id", "transaction_id.commission_amount")
    def _compute_commission_amount(self):
        for move in self:
            if move.transaction_id:
                move.commission_amount = move.transaction_id.commission_amount or 0.0
            else:
                move.commission_amount = 0.0

    @api.depends("freight_charged", "freight_actual")
    def _compute_freight_variance(self):
        for move in self:
            move.freight_variance = (move.freight_charged or 0.0) - (move.freight_actual or 0.0)

    # ── Actions ───────────────────────────────────────────────
    def calculate_penalties(self):
        """Calculate and apply penalties based on penalty rules."""
        penalty_rule_model = self.env["plasticos.penalty.rule"]

        for move in self:
            if move.has_penalty:
                continue

            variance = move.weight_variance_percent or 0.0
            days_late = 0
            if move.invoice_date_due and move.invoice_date:
                delta = fields.Date.today() - move.invoice_date_due
                days_late = max(0, delta.days) if delta.days > 0 else 0

            result = penalty_rule_model.calculate_penalty(
                move,
                variance_percent=variance,
                days_late=days_late,
            )

            if result:
                move.write(
                    {
                        "has_penalty": True,
                        "penalty_amount": result["amount"],
                        "penalty_reason": result["reason"],
                        "penalty_rule_id": result.get("rule_id"),
                    }
                )
                move.message_post(body=f"Penalty calculated: ${result['amount']:.2f} - {result['reason']}")

    def action_approve_weight_variance(self):
        """Approve weight variance for this invoice."""
        for move in self:
            if move.weight_variance_percent > 0 and not move.weight_variance_approved:
                move.write(
                    {
                        "weight_variance_approved": True,
                        "weight_variance_approved_by": self.env.user.id,
                        "weight_variance_approved_date": fields.Datetime.now(),
                    }
                )
                move.message_post(
                    body=f"Weight variance of {move.weight_variance_percent:.1f}% approved by {self.env.user.name}"
                )

    def action_reconcile_freight(self):
        """Mark freight as reconciled and create adjustment if needed."""
        for move in self:
            if move.freight_variance != 0:
                move.reconciliation_status = "reconciled"
                if move.freight_variance > 0:
                    move.message_post(
                        body=f"Freight reconciled: ${move.freight_variance:.2f} profit (charged > actual)"
                    )
                else:
                    move.message_post(
                        body=f"Freight reconciled: ${abs(move.freight_variance):.2f} loss (actual > charged)"
                    )


class InvoiceAdjustment(models.Model):
    """Invoice adjustment line for automatic adjustments."""

    _name = "plasticos.invoice.adjustment"
    _description = "Invoice Adjustment"
    _order = "id"

    move_id = fields.Many2one(
        "account.move",
        string="Invoice",
        required=True,
        ondelete="cascade",
    )

    adjustment_type = fields.Selection(
        [
            ("penalty", "Penalty"),
            ("weight_variance", "Weight Variance"),
            ("freight", "Freight Adjustment"),
            ("commission", "Commission"),
            ("other", "Other"),
        ],
        string="Type",
        required=True,
    )

    amount = fields.Float(
        string="Amount",
        digits="Product Price",
        required=True,
    )

    account_id = fields.Many2one(
        "account.account",
        string="Account",
        help="Account for the adjustment entry",
    )

    reason = fields.Char(string="Reason")
    applied = fields.Boolean(string="Applied", default=False)

    def action_apply_adjustment(self):
        """Apply the adjustment (placeholder for actual journal entry creation)."""
        for adj in self:
            if not adj.applied:
                adj.applied = True
                adj.move_id.message_post(body=f"Adjustment applied: {adj.adjustment_type} - ${adj.amount:.2f}")
