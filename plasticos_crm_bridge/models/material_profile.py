import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PlasticosMaterialProfileCrmBridge(models.Model):
    _inherit = "plasticos.material.profile"

    # ── Match Statistics ──────────────────────────────────────────
    match_count = fields.Integer(
        string="Total Matches",
        compute="_compute_match_stats",
        store=False,
    )
    best_match_score = fields.Float(
        string="Best Match Score",
        digits=(5, 2),
        compute="_compute_match_stats",
        store=False,
    )
    pending_match_count = fields.Integer(
        string="Pending Matches",
        compute="_compute_match_stats",
        store=False,
    )

    # ── Transaction Statistics ────────────────────────────────────
    transaction_count = fields.Integer(
        string="Transactions",
        compute="_compute_tx_stats",
        store=False,
    )
    total_revenue = fields.Float(
        string="Total Revenue",
        digits=(16, 2),
        compute="_compute_tx_stats",
        store=False,
    )
    last_pickup_date = fields.Datetime(
        string="Last Pickup Date",
        compute="_compute_tx_stats",
        store=False,
    )

    def _compute_match_stats(self):
        Intake = self.env["plasticos.intake"]
        MatchResult = self.env["plasticos.match.result"]
        for rec in self:
            intakes = Intake.search(
                [
                    ("partner_id", "=", rec.partner_id.id),
                    ("polymer_id", "=", rec.polymer_id.id),
                ]
            )
            if intakes:
                results = MatchResult.search(
                    [("intake_id", "in", intakes.ids)]
                )
                rec.match_count = len(results)
                rec.best_match_score = max(results.mapped("score"), default=0.0)
                rec.pending_match_count = len(
                    results.filtered(lambda r: r.state == "pending")
                )
            else:
                rec.match_count = 0
                rec.best_match_score = 0.0
                rec.pending_match_count = 0

    def _compute_tx_stats(self):
        Transaction = self.env["plasticos.transaction"]
        for rec in self:
            txs = Transaction.search(
                [
                    "|",
                    ("supplier_profile_id", "=", rec.id),
                    ("buyer_profile_id", "=", rec.id),
                ]
            )
            rec.transaction_count = len(txs)
            rec.total_revenue = sum(txs.mapped("revenue_total"))

            # Find last pickup date from linked loads
            loads = txs.mapped("load_id").filtered(
                lambda ld: ld.pickup_datetime
                and ld.state in ("picked_up", "delivered", "closed")
            )
            pickup_dates = loads.mapped("pickup_datetime")
            rec.last_pickup_date = max(pickup_dates) if pickup_dates else False
