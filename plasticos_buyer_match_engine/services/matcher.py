"""Deterministic buyer-matching engine (Stage 1 of two-stage pipeline).

Matches an intake's material profile against buyer capability lanes.
Gates: identity (source_type + polymer + form) → quality → volume →
compliance → geo.  Results are written to plasticos.match.result and
sorted by distance ascending (closest first).

ARCHITECTURE:
    Stage 1 (THIS): Deterministic hard gates — exact match on polymer, form,
                    source_type. Eliminates incompatible buyers.
    Stage 2 (Graph): Range-based gates (MFI, density) + soft signals + scoring.

WHY MATCHER DOESN'T CHECK MFI:
    MFI is a RANGE (min/max), not an exact match. Ranges require the Graph
    Service which can do inequality comparisons in Cypher. This matcher
    handles deterministic gates only.
"""

import logging
from math import atan2, cos, radians, sin, sqrt

_logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# FORM EQUIPMENT CAPABILITY MATRIX
# ═══════════════════════════════════════════════════════════════════════════
# Equipment determines what forms a facility can ACTUALLY process:
#   - Granulator/Shredder: Can break down bales, parts, lumps → regrind
#   - Pelletizer/Extruder (no granulator): Can only process regrind/flake/pellet
#   - Compounder: For blending additives, NOT for form conversion
# ═══════════════════════════════════════════════════════════════════════════

# Forms that require size reduction equipment (granulator/shredder)
FORMS_REQUIRING_SIZE_REDUCTION = frozenset(["bales", "parts", "lump", "rollstock", "sheet"])

# Forms that are already processed (no size reduction needed)
FORMS_PRE_PROCESSED = frozenset(["regrind", "flake", "pellet", "powder"])


class PlasticosMatcher:
    """Stateless service — instantiate with an Odoo env, call match().

    This is Stage 1 of the two-stage matching pipeline. It eliminates
    buyers that cannot physically accept the material based on:
        - Exact polymer match
        - Form compatibility (based on equipment)
        - Source type match
        - Quality gates (contamination, moisture)
        - Volume gates (min/max lot size)
        - Compliance gates (food/medical grade)
        - Geo gate (radius)

    Survivors are passed to Stage 2 (Graph Service) for refined analysis.
    """

    def __init__(self, env):
        self.env = env

    # ── Public API ───────────────────────────────────────────

    def match(self, intake, facility_ids=None):
        """Run the full matching pipeline for a single intake record.

        Args:
            intake: a ``plasticos.intake`` recordset (single record).
            facility_ids: optional list of facility partner IDs to filter to.
                          Used when running as Stage 1 before Graph Service.

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
        ]

        # Form matching: either exact match OR equipment-derived capability
        # We'll filter by equipment in Python after fetching candidates
        # to allow equipment-based form acceptance

        if facility_ids:
            domain.append(("facility_id.partner_id", "in", facility_ids))

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
        facility = cap.facility_id

        # ── Form gate (equipment-based) ───────────────────────
        # Check if facility can handle the material's form based on equipment
        intake_form = material.form
        if not self._can_handle_form(facility, intake_form, cap.form):
            return self._reject(cap, "form_not_compatible")

        # Quality gate: contamination
        if (
            cap.max_contamination_pct
            and material.contamination_percent
            and material.contamination_percent > cap.max_contamination_pct
        ):
            return self._reject(cap, "contamination_exceeds_limit")

        # Quality gate: moisture
        if cap.max_moisture_pct and material.moisture_percent and material.moisture_percent > cap.max_moisture_pct:
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
        if facility.partner_id:
            buyer_lat = getattr(facility.partner_id, "partner_latitude", 0) or 0
            buyer_lon = getattr(facility.partner_id, "partner_longitude", 0) or 0

        distance = self._distance_miles(seller_lat, seller_lon, buyer_lat, buyer_lon)

        if cap.radius_miles and distance > cap.radius_miles:
            return self._reject(cap, "outside_radius")

        return {
            "eligible": True,
            "capability": cap,
            "facility_id": facility.partner_id.id if facility.partner_id else None,
            "distance_miles": distance,
        }

    def _can_handle_form(self, facility, intake_form, capability_form):
        """Check if facility can handle the intake form based on equipment.

        Logic:
            1. Exact match on capability.form always passes
            2. If intake form requires size reduction (bales, parts, lumps):
               - Facility MUST have granulator OR shredder
            3. If intake form is pre-processed (regrind, flake, pellet):
               - Facility with pelletizer/extruder can handle it
            4. Equipment-derived capability expands what facility can accept

        Args:
            facility: plasticos.facility.profile record
            intake_form: form from material profile (e.g., 'bales')
            capability_form: form declared in buyer.capability lane

        Returns:
            bool: True if facility can handle the form
        """
        # Exact match on declared capability always passes
        if intake_form == capability_form:
            return True

        # Check equipment-derived capability
        acceptable_forms = self._derive_acceptable_forms(facility)
        return intake_form in acceptable_forms

    def _derive_acceptable_forms(self, facility):
        """Derive forms a facility can accept based on equipment.

        Equipment → Form Capability:
            - Granulator/Shredder: Can break down ANY form to regrind
            - Extruder: Can process regrind/flake → pellet
            - Explicit handles_* flags: Always accepted

        NULL Handling (per BOOLEAN_FIELD_MATRIX.md):
            - NULL equipment = incomplete profile, NOT "doesn't have"
            - NULL equipment → allow through (don't exclude)
            - Only exclude if equipment is explicitly False AND form requires it

        Returns:
            set: Forms this facility can accept
        """
        forms = set()

        # Get equipment values (None = unknown, True = has, False = doesn't have)
        has_granulator = getattr(facility, "has_granulator", None)
        has_shredder = getattr(facility, "has_shredder", None)
        has_extruder = getattr(facility, "has_extruder", None)

        # Granulator/shredder = can break down ANY form to regrind
        # True = explicitly has; None = unknown (allow through)
        if has_granulator is True or has_shredder is True:
            forms.update(["bales", "parts", "lump", "rollstock", "sheet", "regrind", "flake", "pellet", "purge"])
        elif has_granulator is None and has_shredder is None:
            # NULL equipment = incomplete profile, allow ALL forms through
            # (Graph Service will do refined filtering with NULL handling)
            forms.update(["bales", "parts", "lump", "rollstock", "sheet", "regrind", "flake", "pellet", "purge"])

        # Extruder = can process regrind/flake → pellet
        # Only add these if we haven't already added all forms above
        if has_extruder is True:
            forms.update(["regrind", "flake", "pellet"])
        elif has_extruder is None and not forms:
            # NULL extruder + no granulator/shredder = allow pre-processed forms
            forms.update(["regrind", "flake", "pellet"])

        # Always can handle what they explicitly declared (True only, not NULL)
        if getattr(facility, "handles_bales", None) is True:
            forms.add("bales")
        if getattr(facility, "handles_regrind", None) is True:
            forms.add("regrind")
        if getattr(facility, "handles_pellet", None) is True:
            forms.add("pellet")
        if getattr(facility, "handles_flake", None) is True:
            forms.add("flake")
        if getattr(facility, "handles_rollstock", None) is True:
            forms.add("rollstock")

        return forms

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

        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
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
