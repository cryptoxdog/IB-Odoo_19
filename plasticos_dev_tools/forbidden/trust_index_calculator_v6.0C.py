# ============================================================
# File: trust_index_calculator_v4.0C.py
# Domain: core
# Version: 4.0C
# Created: 2025-10-28
# Author: Igor Beylin
# Purpose: Compute and maintain buyer trust scores for use in offer logic,
#          pricing confidence, and relational intelligence analytics.
# ============================================================

"""
Trust Index Calculator
======================
This module calculates, updates, and tracks the composite trust score
for each buyer in the system. The Trust Index reflects a weighted balance
of quantitative performance data and qualitative relationship signals.

Designed for Odoo 19 integration under model: `plasticos.buyer.profile`.
"""

import datetime

from odoo import api, fields, models


class TrustIndexCalculator(models.Model):
    _name = "plasticos.trust.calculator"
    _description = "Trust Index Calculator and Updater"

    buyer_id = fields.Many2one("plasticos.buyer.profile", string="Buyer")
    trust_index = fields.Float("Trust Index", digits=(5, 2), default=50.0)
    last_update = fields.Datetime("Last Updated")
    reliability_score = fields.Float("Reliability", digits=(5, 2))
    payment_score = fields.Float("Payment Behavior", digits=(5, 2))
    engagement_score = fields.Float("Engagement", digits=(5, 2))
    sentiment_score = fields.Float("Sentiment", digits=(5, 2))
    adjustment_factor = fields.Float("Manual Adjustment", digits=(4, 2), default=0.0)

    # ------------------------------------------------------------
    # Weighted Calculation Logic
    # ------------------------------------------------------------
    @api.model
    def compute_trust_index(self, buyer_id):
        buyer = self.env["plasticos.buyer.profile"].browse(buyer_id)
        history = self._fetch_buyer_history(buyer)

        reliability = self._score_reliability(history)
        payment = self._score_payment(history)
        engagement = self._score_engagement(history)
        sentiment = self._score_sentiment(history)

        # Composite weighting (modifiable in env var policy)
        trust_index = reliability * 0.35 + payment * 0.30 + engagement * 0.20 + sentiment * 0.15

        record = self.create(
            {
                "buyer_id": buyer.id,
                "trust_index": trust_index,
                "reliability_score": reliability,
                "payment_score": payment,
                "engagement_score": engagement,
                "sentiment_score": sentiment,
                "last_update": datetime.datetime.now(),
            }
        )

        buyer.trust_index = trust_index
        return trust_index

    # ------------------------------------------------------------
    # Metric Extraction Methods
    # ------------------------------------------------------------
    def _fetch_buyer_history(self, buyer):
        """Pulls order, payment, and correspondence logs for scoring."""
        orders = self.env["sale.order"].search([("partner_id", "=", buyer.partner_id.id)])
        payments = self.env["account.payment"].search([("partner_id", "=", buyer.partner_id.id)])
        communications = self.env["mail.message"].search(
            [("model", "=", "res.partner"), ("res_id", "=", buyer.partner_id.id)]
        )
        return {"orders": orders, "payments": payments, "messages": communications}

    def _score_reliability(self, history):
        total_orders = len(history["orders"])
        fulfilled = len([o for o in history["orders"] if o.state == "sale"])
        return 100 * (fulfilled / total_orders) if total_orders else 50.0

    def _score_payment(self, history):
        payments = history["payments"]
        if not payments:
            return 50.0
        on_time = len([p for p in payments if p.payment_date <= p.invoice_ids.invoice_date_due])
        ratio = on_time / len(payments)
        return 50 + (ratio * 50)

    def _score_engagement(self, history):
        msgs = history["messages"]
        recent_msgs = [m for m in msgs if (datetime.datetime.now() - m.date).days < 90]
        return min(len(recent_msgs) * 2, 100)

    def _score_sentiment(self, history):
        """Placeholder for NLP sentiment analysis on correspondence text."""
        # Placeholder baseline until sentiment engine connected.
        return 70.0

    # ------------------------------------------------------------
    # Scheduled Recalculation
    # ------------------------------------------------------------
    @api.model
    def scheduled_recalculation(self):
        """Nightly cron to refresh trust indices for all buyers."""
        buyers = self.env["plasticos.buyer.profile"].search([])
        for buyer in buyers:
            self.compute_trust_index(buyer.id)
        self.env["plasticos.decision.ledger"].create(
            {
                "timestamp": datetime.datetime.now(),
                "actor": "PlasticOS Trust Index Calculator",
                "context": "system",
                "message": f"Trust Index recalculated for {len(buyers)} buyers.",
            }
        )


# End of File
# ============================================================
