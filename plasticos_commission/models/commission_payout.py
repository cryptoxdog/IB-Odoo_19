import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PlasticosCommissionPayout(models.Model):
    """Commission payout record — one per sales rep per period.

    Aggregates commission_locked_amount from closed transactions assigned
    to a rep within a date range. Full audit trail via mail.thread.

    Workflow:  draft → confirmed → paid
               draft → cancelled
    """

    _name = "plasticos.commission.payout"
    _description = "Commission Payout"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_end desc, sales_rep_id"
    _rec_name = "name"

    name = fields.Char(required=True, copy=False, readonly=True, default="/", index=True)

    # ── Rep + Period ────────────────────────────────────────────────────────
    sales_rep_id = fields.Many2one(
        "res.users",
        string="Sales Rep",
        required=True,
        tracking=True,
        index=True,
        domain="[('share', '=', False)]",
    )
    commission_rule_id = fields.Many2one(
        "plasticos.commission.rule",
        string="Commission Rule",
        tracking=True,
        help="Primary rule used for this period. Informational only.",
    )
    period_start = fields.Date(required=True, tracking=True)
    period_end = fields.Date(required=True, tracking=True)

    # ── Amounts ─────────────────────────────────────────────────────────────
    transaction_count = fields.Integer(string="# Transactions", compute="_compute_totals", store=True)
    gross_margin_total = fields.Float(
        string="Total Gross Margin", compute="_compute_totals", store=True, digits="Product Price"
    )
    commission_due = fields.Float(
        string="Commission Due",
        compute="_compute_totals",
        store=True,
        digits="Product Price",
        help="Sum of commission_locked_amount from linked closed transactions.",
    )
    commission_paid = fields.Float(
        string="Commission Paid",
        digits="Product Price",
        tracking=True,
        help="Actual amount disbursed. Defaults to commission_due on mark_paid.",
    )
    commission_balance = fields.Float(
        string="Balance Due", compute="_compute_balance", store=True, digits="Product Price"
    )
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id, readonly=True)

    # ── Linked Transactions ──────────────────────────────────────────────────
    transaction_ids = fields.Many2many(
        "plasticos.transaction",
        "commission_payout_tx_rel",
        "payout_id",
        "transaction_id",
        string="Transactions",
        domain="[('state', '=', 'closed'), ('commission_locked', '=', True)]",
    )

    # ── Payment Info ─────────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed — Awaiting Payment"),
            ("paid", "Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    payment_date = fields.Date(tracking=True)
    payment_reference = fields.Char(
        string="Payment Reference", tracking=True, help="Check number, wire reference, or payroll batch ID."
    )
    notes = fields.Text()

    # ── Constraints ──────────────────────────────────────────────────────────
    @api.constrains("period_start", "period_end")
    def _check_period(self):
        for rec in self:
            if rec.period_start and rec.period_end and rec.period_start > rec.period_end:
                raise UserError("Period start must be before period end.")

    # ── Computed ─────────────────────────────────────────────────────────────
    @api.depends("transaction_ids", "transaction_ids.commission_locked_amount", "transaction_ids.gross_margin")
    def _compute_totals(self):
        for rec in self:
            txs = rec.transaction_ids
            rec.transaction_count = len(txs)
            rec.gross_margin_total = sum(txs.mapped("gross_margin"))
            rec.commission_due = sum(txs.mapped("commission_locked_amount"))

    @api.depends("commission_due", "commission_paid")
    def _compute_balance(self):
        for rec in self:
            rec.commission_balance = (rec.commission_due or 0.0) - (rec.commission_paid or 0.0)

    # ── Sequence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("plasticos.commission.payout") or "/"
        return super().create(vals_list)

    # ── State Actions ─────────────────────────────────────────────────────────
    def action_confirm(self):
        """Lock the transaction list and confirm the payout amount."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft payouts can be confirmed.")
            if not rec.transaction_ids:
                raise UserError("Cannot confirm a payout with no transactions linked.")
            rec.state = "confirmed"
            rec.message_post(
                body=(
                    f"Payout confirmed: {rec.transaction_count} transaction(s), "
                    f"${rec.commission_due:,.2f} due to {rec.sales_rep_id.name}."
                ),
                message_type="notification",
            )

    def action_mark_paid(self):
        """Record payment. Sets commission_paid = commission_due and advances state."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError("Only confirmed payouts can be marked as paid.")
            if not rec.payment_date:
                raise UserError("Please set a Payment Date before marking as paid.")
            rec.commission_paid = rec.commission_due
            rec.state = "paid"
            rec.message_post(
                body=(
                    f"Commission paid: ${rec.commission_paid:,.2f} on {rec.payment_date} "
                    f"(ref: {rec.payment_reference or 'N/A'})."
                ),
                message_type="notification",
            )

    def action_reset_draft(self):
        for rec in self:
            if rec.state == "paid":
                raise UserError("Paid payouts cannot be reset.")
            rec.state = "draft"

    def action_cancel(self):
        for rec in self:
            if rec.state == "paid":
                raise UserError("Paid payouts cannot be cancelled.")
            rec.state = "cancelled"

    # ── Generator Helper ──────────────────────────────────────────────────────
    @api.model
    def action_generate_for_rep(self, sales_rep_id, period_start, period_end):
        """Find all closed, unpaid transactions for a rep and create a draft payout.

        Safe to call from cron or UI wizard.
        Returns new payout record, or False if no qualifying transactions found.
        """
        already_paid_tx_ids = self.search([("state", "in", ["confirmed", "paid"])]).mapped("transaction_ids").ids

        txs = self.env["plasticos.transaction"].search(
            [
                ("user_id", "=", sales_rep_id),
                ("state", "=", "closed"),
                ("commission_locked", "=", True),
                ("commission_locked_amount", ">", 0),
                ("id", "not in", already_paid_tx_ids),
            ]
        )
        if not txs:
            return False

        return self.create(
            {
                "sales_rep_id": sales_rep_id,
                "period_start": period_start,
                "period_end": period_end,
                "transaction_ids": [(6, 0, txs.ids)],
            }
        )
