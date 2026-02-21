"""Deterministic buyer-matching engine.

Matches an intake's material profile against buyer capability lanes.
Gates: identity (source_type + polymer + form) → quality → volume →
compliance → geo.  Results are written to plasticos.match.result and
sorted by distance ascending (closest first).
"""

import logging
from math import radians, sin, cos, sqrt, atan2

_logger = logging.getLogger(__name__)


class PlasticosMatcher:
    """Stateless service — instantiate with an Odoo env, call match()."""

    def __init__(self, env):
        self.env = env

    # ── Public API ───────────────────────────────────────────

    def match(self, intake):
        """Run the full matching pipeline for a single intake record.

        Args:
            intake: a ``plasticos.intake`` recordset (single record).

        Returns:
            list[dict]: eligible matches sorted by distance_miles ascending.

        Raises:
            ValueError: if intake has no linked material_profile_id.
        """
        if not intake.material_profile_id:
            raise ValueError("Material profile required before matching.")

        material = intake.material_profile_id

        # ── Stage 1: identity filter (DB-level) ─────────────
        domain = [
            ("active", "=", True),
            ("source_type", "=", material.source_type),
            ("polymer", "=", material.polymer),
            ("form", "=", material.form),
        ]
        capabilities = self.env["plasticos.buyer.capability"].search(domain)

        _logger.info(
            "Buyer match: intake=%s  identity candidates=%d",
            intake.name,
            len(capabilities),
        )

        # ── Stage 2: gate evaluation (Python-level) ─────────
        matches = []
        rejections = []

        for cap in capabilities:
            result = self._evaluate(cap, material, intake)
            if result["eligible"]:
                matches.append(result)
            else:
                rejections.append(result)

        # ── Stage 3: rank by distance (closest first) ───────
        matches.sort(key=lambda x: x["distance_miles"])

        _logger.info(
            "Buyer match: intake=%s  eligible=%d  rejected=%d",
            intake.name,
            len(matches),
            len(rejections),
        )

        # ── Stage 4: persist to match.result ─────────────────
        self._write_match_results(intake, matches)

        return matches

    # ── Gate evaluation ──────────────────────────────────────

    def _evaluate(self, cap, material, intake):
        """Evaluate a single capability against the intake/material.

        Returns a dict with at minimum ``eligible`` (bool).
        If eligible, includes ``capability`` and ``distance_miles``.
        If rejected, includes ``reason``.
        """

        # Quality gate: contamination
        if (
            cap.max_contamination_pct
            and material.contamination_percent
            and material.contamination_percent > cap.max_contamination_pct
        ):
            return self._reject(cap, "contamination_exceeds_limit")

        # Quality gate: moisture
        if (
            cap.max_moisture_pct
            and material.moisture_percent
            and material.moisture_percent > cap.max_moisture_pct
        ):
            return self._reject(cap, "moisture_exceeds_limit")

        # Volume gate: minimum
        quantity = getattr(intake, "quantity_per_load_lbs", 0) or 0
        if cap.min_volume_lbs and quantity < cap.min_volume_lbs:
            return self._reject(cap, "volume_below_min")

        # Volume gate: maximum
        if cap.max_volume_lbs and quantity > cap.max_volume_lbs:
            return self._reject(cap, "volume_above_max")

        # Compliance gate: food grade
        if cap.requires_food_grade and not material.food_grade:
            return self._reject(cap, "food_grade_required")

        # Compliance gate: medical grade
        if cap.requires_medical_grade and not material.medical_grade:
            return self._reject(cap, "medical_grade_required")

        # Geo gate: distance
        seller_lat = getattr(intake, "lat", 0) or 0
        seller_lon = getattr(intake, "lon", 0) or 0

        if not seller_lat and intake.partner_id:
            seller_lat = getattr(intake.partner_id, "partner_latitude", 0) or 0
        if not seller_lon and intake.partner_id:
            seller_lon = getattr(intake.partner_id, "partner_longitude", 0) or 0

        buyer_lat = 0
        buyer_lon = 0
        if cap.facility_id.partner_id:
            buyer_lat = getattr(cap.facility_id.partner_id, "partner_latitude", 0) or 0
            buyer_lon = getattr(cap.facility_id.partner_id, "partner_longitude", 0) or 0

        distance = self._distance_miles(seller_lat, seller_lon, buyer_lat, buyer_lon)

        if cap.radius_miles and distance > cap.radius_miles:
            return self._reject(cap, "outside_radius")

        return {
            "eligible": True,
            "capability": cap,
            "distance_miles": distance,
        }

    # ── Helpers ──────────────────────────────────────────────

    def _reject(self, cap, reason):
        return {
            "eligible": False,
            "capability": cap,
            "reason": reason,
        }

    def _distance_miles(self, lat1, lon1, lat2, lon2):
        """Haversine distance in miles.  Returns 99999 if coords missing."""
        if not lat1 or not lon1 or not lat2 or not lon2:
            return 99999.0

        R = 3958.8  # Earth radius in miles

        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)

        a = (
            sin(dlat / 2) ** 2
            + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        )
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    def _write_match_results(self, intake, matches):
        """Persist eligible matches to plasticos.match.result.

        Clears previous results for this intake, then creates new ones.
        Score = max(0, 100 - distance_miles) so closer = higher score.
        """
        Match = self.env["plasticos.match.result"]

        # Clear stale results
        Match.search([("intake_id", "=", intake.id)]).unlink()

        for rank, m in enumerate(matches, start=1):
            cap = m["capability"]
            dist = m["distance_miles"]
            score = max(0.0, 100.0 - dist)

            Match.create(
                {
                    "intake_id": intake.id,
                    "buyer_partner_id": cap.facility_id.partner_id.id,
                    "facility_profile_id": cap.facility_id.id,
                    "score": score,
                    "confidence": 100.0,
                    "score_breakdown": {
                        "rank": rank,
                        "distance_miles": round(dist, 2),
                        "source_type": cap.source_type,
                        "polymer": cap.polymer,
                        "form": cap.form,
                        "process_type": cap.process_type or "any",
                    },
                    "match_reasoning": (
                        f"Rank #{rank}: {cap.facility_id.partner_id.name} — "
                        f"{round(dist, 1)} mi, "
                        f"{cap.polymer}/{cap.form}/{cap.source_type}"
                    ),
                    "state": "pending",
                }
            )
