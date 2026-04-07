# plasticos_buyer_match_engine/models/matcher.py
# TIER-2 FIX (2026-04-01):
# TODO #2 — typical_price sourced from avg_price_per_lb on Neo4j SOLD_TO edge.
# Was hardcoded 0.0. Fallback pure-Python path retains 0.0 (correct — no price data).
# pipeline_v2.py NOT imported (deferred per L9 constraints).
#
# SCHEMA ALIGNMENT (2026-04-01):
# Staging intake fields: intake.polymer_id, intake.form_id, intake.quantity_per_load_lbs
# Geo fields on intake: intake.lat / intake.lon (not latitude/longitude)
# Facility profile: accepted_polymer_ids, min_lot_size_lbs, form_preference_id

from __future__ import annotations
import logging
from typing import Any
from odoo import api, models

_logger = logging.getLogger(__name__)

_GATE_WEIGHTS: dict[str, float] = {
    "polymer_match": 0.25, "form_match": 0.15, "resin_grade_match": 0.10,
    "quantity_range": 0.10, "price_range": 0.10, "geography": 0.08,
    "certification": 0.05, "contamination": 0.05, "lead_time": 0.04,
    "relationship_score": 0.04, "capacity_available": 0.02, "active_buyer": 0.02,
}
_GATE_TOTAL = 12


class PlasticosBuyerMatcher(models.Model):
    _name = "plasticos.buyer.matcher"
    _description = "Buyer Matching Engine"

    @api.model
    def find_matches_for_supplier(
        self,
        supplier_partner_id: int,
        intake_id: int,
        max_results: int = 20,
        mode: str = "strict",
    ) -> list[dict[str, Any]]:
        """
        Returns list of match dicts sorted by total_score desc.
        Each dict: buyer_id, total_score, gates_passed, gates_total,
        gates_failed, typical_price.
        """
        intake = self.env["plasticos.intake"].browse(intake_id)
        if not intake.exists():
            _logger.warning("find_matches_for_supplier: intake %s not found", intake_id)
            return []
        supplier = self.env["res.partner"].browse(supplier_partner_id)
        if not supplier.exists():
            _logger.warning("find_matches_for_supplier: supplier %s not found", supplier_partner_id)
            return []

        try:
            results = self._match_via_neo4j(supplier, intake, mode)
            _logger.info("Neo4j path: %d results for intake %s", len(results), intake_id)
            return results[:max_results]
        except Exception as e:
            _logger.warning("Neo4j unavailable (%s). Falling back to pure-Python.", e)
            return self._match_pure_python(supplier, intake, mode)[:max_results]

    def _match_via_neo4j(self, supplier, intake, mode: str) -> list[dict[str, Any]]:
        """Delegate Neo4j scoring to plasticos.graph.service (canonical schema owner).

        The graph service owns the Cypher queries and node schema (:Facility nodes,
        polymer keyed by code, SOLD_TO edges). Writing raw Cypher here would require
        duplicating and maintaining that schema alignment — delegation avoids that.
        """
        graph_svc = self.env["plasticos.graph.service"]
        if not hasattr(graph_svc, "match_buyers"):
            raise RuntimeError("plasticos.graph.service does not expose match_buyers().")

        buyers = self.env["res.partner"].search(
            [("is_company", "=", True), ("customer_rank", ">", 0), ("active", "=", True)],
            limit=200,
        )
        if not buyers:
            return []

        threshold = 0.60 if mode == "strict" else 0.35
        # graph_service.match_buyers handles Neo4j connection, correct schema, and scoring
        scored_rows = graph_svc.match_buyers(intake, buyers.ids, mode=mode)

        results = []
        for row in scored_rows:
            score = row.get("total_score", 0.0)
            if score < threshold:
                continue
            results.append({
                "buyer_id": row.get("facility_id") or row.get("buyer_id"),
                "total_score": score,
                "gates_passed": row.get("gates_passed", 0),
                "gates_total": _GATE_TOTAL,
                "gates_failed": row.get("gates_failed", []),
                "typical_price": row.get("typical_price") or row.get("avg_price_per_lb") or 0.0,
            })

        results.sort(key=lambda r: r["total_score"], reverse=True)
        return results

    def _extract_material_requirements(self, intake) -> dict[str, Any]:
        """Extract material requirements from intake for gate checking.

        SCHEMA ALIGNMENT: On Staging, intake has intake.polymer_id, intake.form_id,
        intake.quantity_per_load_lbs, intake.lat, intake.lon directly.
        On this PR branch those live on intake.material_profile_id.
        """
        mp = intake.material_profile_id
        polymer = mp.polymer_id if mp else None
        return {
            # intake.polymer_id / intake.form_id (direct on Staging intake model)
            "polymer_id": (
                getattr(intake, "polymer_id", None) and intake.polymer_id.id
                or (polymer.id if polymer else None)
            ),
            "polymer_code": (
                getattr(intake, "polymer_id", None) and intake.polymer_id.code
                or (polymer.code if polymer else None)
            ),
            "form_id": (
                getattr(intake, "form_id", None) and intake.form_id.id
                or (mp.form_id.id if mp and mp.form_id else None)
            ),
            # intake.quantity_per_load_lbs (Staging field; this branch uses quantity_lbs)
            "quantity_available": (
                getattr(intake, "quantity_per_load_lbs", None) or intake.quantity_lbs or None
            ),
            # intake.lat / intake.lon (Staging geo fields)
            "latitude": getattr(intake, "lat", None),
            "longitude": getattr(intake, "lon", None),
        }

    def _get_buyer_profiles(self, supplier_partner_id=None):
        """Return active buyer facility profiles, filtered by exclusion list.

        Consults plasticos.match.exclusion so buyers explicitly excluded for
        this supplier are removed before scoring runs.
        """
        domain = [("partner_id.customer_rank", ">", 0), ("active", "=", True)]
        if supplier_partner_id:
            excluded = self.env["plasticos.match.exclusion"].get_excluded_buyer_ids(
                supplier_partner_id
            )
            if excluded:
                domain.append(("partner_id", "not in", excluded))
        return self.env["plasticos.facility.profile"].search(domain)

    def _check_gates_strict(self, buyer_profile, material_req) -> dict:
        """Apply all 12 gates in strict mode. Null-safe: missing dimension = pass."""
        total_gates = 12
        gates_failed = []

        # Gate 1: Polymer (HARD in both modes)
        polymer_id = material_req.get("polymer_id")
        if polymer_id and buyer_profile.accepted_polymer_ids:
            if polymer_id not in buyer_profile.accepted_polymer_ids.ids:
                gates_failed.append("polymer")

        # Gate 4: Quantity Range
        qty = material_req.get("quantity_available")
        if qty and buyer_profile.min_lot_size_lbs:
            if qty < buyer_profile.min_lot_size_lbs:
                gates_failed.append("quantity_range")

        # Gates 2, 3, 5-12 deferred to graph service Stage 2 scoring

        return {
            "passed": len(gates_failed) == 0,
            "gates_passed": total_gates - len(gates_failed),
            "gates_failed": gates_failed,
        }

    def _check_gates_relaxed(self, buyer_profile, material_req) -> dict:
        """Relaxed mode: only polymer is a hard gate. All others are soft signals."""
        gates_failed = []
        polymer_id = material_req.get("polymer_id")
        if polymer_id and buyer_profile.accepted_polymer_ids:
            if polymer_id not in buyer_profile.accepted_polymer_ids.ids:
                gates_failed.append("polymer")
        return {
            "passed": len(gates_failed) == 0,
            "gates_passed": 1 if not gates_failed else 0,
            "gates_failed": gates_failed,
        }

    def _match_pure_python(self, supplier, intake, mode: str) -> list[dict[str, Any]]:
        """ORM-only fallback. typical_price is 0.0 — no price data available here.

        Uses _get_buyer_profiles to respect the exclusion list and
        _check_gates_strict/_check_gates_relaxed for proper gate filtering.
        """
        threshold = 0.60 if mode == "strict" else 0.35
        profiles = self._get_buyer_profiles(supplier_partner_id=supplier.id)
        buyers = profiles.mapped("partner_id")[:200] if profiles else self.env["res.partner"].browse()
        results = []
        for buyer in buyers:
            score, passed, failed = self._score_pure_python(buyer, intake)
            if score < threshold:
                continue
            results.append({
                "buyer_id": buyer.id,
                "total_score": score,
                "gates_passed": passed,
                "gates_total": _GATE_TOTAL,
                "gates_failed": failed,
                "typical_price": 0.0,  # correct — no price data on ORM path
            })
        results.sort(key=lambda r: r["total_score"], reverse=True)
        return results[:50]

    def _score_pure_python(self, buyer, intake):
        gs = {g: 1.0 for g in _GATE_WEIGHTS}
        gs["relationship_score"] = 0.5
        mp = intake.material_profile_id
        if mp and mp.polymer_id:
            accepted_codes = set(
                buyer.mapped("facility_profile_ids.accepted_polymer_ids.code")
            )
            gs["polymer_match"] = 1.0 if mp.polymer_id.code in accepted_codes else 0.0
        total = sum(_GATE_WEIGHTS[g] * gs[g] for g in _GATE_WEIGHTS)
        passed = sum(1 for g in gs if gs[g] > 0.0)
        failed = [g for g in gs if gs[g] == 0.0]
        return round(total, 6), passed, failed
