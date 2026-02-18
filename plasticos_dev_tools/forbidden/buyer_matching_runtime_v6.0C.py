# ============================================================
# File: buyer_matching_runtime_v4.0C.py
# Domain: core
# Version: 4.0C
# Created: 2025-10-28
# Author: Igor Beylin
# Purpose: Real-time offer-buyer matching engine leveraging trust,
#          capability, and compatibility metrics to optimize trade routing.
# ============================================================

"""
Buyer Matching Runtime Engine
=============================
Executes dynamic matching logic between offers and buyers.

Integrates with:
- `mack.trust.calculator` for trust index weighting
- `mack.buyer.card` for capability profiling
- `mack.offer.card` for offer metadata and requirements

Runtime matches are stored in transient memory for human review
before dispatch or automation handoff.
"""

import math
import datetime
from odoo import models, fields, api

class BuyerMatchingRuntime(models.Model):
    _name = "mack.buyer.runtime"
    _description = "Buyer Matching Runtime Engine"

    offer_id = fields.Many2one("mack.offer.card", string="Offer")
    buyer_id = fields.Many2one("mack.buyer.card", string="Matched Buyer")
    match_score = fields.Float("Match Score", digits=(5, 2))
    match_reason = fields.Text("Match Rationale")
    timestamp = fields.Datetime("Timestamp", default=datetime.datetime.now)

    # ------------------------------------------------------------
    # Core Matching Logic
    # ------------------------------------------------------------
    @api.model
    def run_match(self, offer_id):
        """Execute the buyer matching pipeline for the given offer."""
        offer = self.env["mack.offer.card"].browse(offer_id)
        buyers = self.env["mack.buyer.card"].search([])
        results = []

        for buyer in buyers:
            score, reason = self._calculate_match_score(buyer, offer)
            results.append({"buyer": buyer, "score": score, "reason": reason})

        # Sort by descending score
        ranked = sorted(results, key=lambda r: r["score"], reverse=True)

        # Log and persist top matches
        for record in ranked[:10]:
            self.create({
                "offer_id": offer.id,
                "buyer_id": record["buyer"].id,
                "match_score": record["score"],
                "match_reason": record["reason"],
            })

        offer.last_match_run = datetime.datetime.now()
        offer.top_buyer = ranked[0]["buyer"].id if ranked else False
        offer.match_confidence = ranked[0]["score"] if ranked else 0.0

        return ranked

    # ------------------------------------------------------------
    # Subscore Calculations
    # ------------------------------------------------------------
    def _calculate_match_score(self, buyer, offer):
        """Weighted combination of capability, geography, trust, and recency."""
        trust = getattr(buyer, "trust_index", 50.0)
        geo = self._score_geographic(buyer, offer)
        cap = self._score_capability(buyer, offer)
        rec = self._score_recency(buyer)
        compat = self._score_material_compatibility(buyer, offer)

        score = (
            trust * 0.30 +
            geo * 0.25 +
            cap * 0.25 +
            rec * 0.10 +
            compat * 0.10
        )

        reason = (
            f"Trust {trust:.1f}, Geo {geo:.1f}, Capability {cap:.1f}, "
            f"Recency {rec:.1f}, Material {compat:.1f}"
        )

        return round(score, 2), reason

    def _score_geographic(self, buyer, offer):
        """Scores based on physical proximity using Haversine distance."""
        if not (buyer.lat and buyer.lon and offer.lat and offer.lon):
            return 50.0
        R = 6371  # Earth radius in km
        lat1, lon1, lat2, lon2 = map(math.radians, [buyer.lat, buyer.lon, offer.lat, offer.lon])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        # Normalize inverse distance
        return max(0, 100 - min(distance / 10, 100))

    def _score_capability(self, buyer, offer):
        """Compares buyer's processing capabilities to offer type."""
        overlap = len(set(buyer.capabilities).intersection(set(offer.requirements)))
        base = (overlap / len(offer.requirements)) * 100 if offer.requirements else 50
        return min(base + (buyer.capacity_factor * 10), 100)

    def _score_recency(self, buyer):
        """Favor buyers who have engaged recently."""
        delta = (datetime.datetime.now() - buyer.last_contact).days if buyer.last_contact else 90
        return max(0, 100 - (delta * 1.1))

    def _score_material_compatibility(self, buyer, offer):
        """Simple material-family compatibility logic."""
        if buyer.material_family == offer.material_family:
            return 100
        elif buyer.material_family.split("_")[0] == offer.material_family.split("_")[0]:
            return 75
        return 40

    # ------------------------------------------------------------
    # Scheduled Automation
    # ------------------------------------------------------------
    @api.model
    def scheduled_match_all(self):
        """Cron job to re-run matches on all active offers nightly."""
        offers = self.env["mack.offer.card"].search([("state", "=", "open")])
        for offer in offers:
            self.run_match(offer.id)
        self.env["mack.decision.ledger"].create({
            "timestamp": datetime.datetime.now(),
            "actor": "Mack Buyer Matching Engine",
            "context": "system",
            "message": f"Auto-match completed for {len(offers)} offers."
        })

# End of File
# ============================================================
