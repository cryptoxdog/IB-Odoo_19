# plasticos_buyer_match_engine/models/matcher.py
# TIER-2 FIX (2026-04-01):
# TODO #2 — typical_price sourced from avg_price_per_lb on Neo4j SOLD_TO edge.
# Was hardcoded 0.0. Fallback pure-Python path retains 0.0 (correct — no price data).
# pipeline_v2.py NOT imported (deferred per L9 constraints).

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

    def _match_pure_python(self, supplier, intake, mode: str) -> list[dict[str, Any]]:
        """ORM-only fallback. typical_price is 0.0 — no price data available here."""
        threshold = 0.60 if mode == "strict" else 0.35
        buyers = self.env["res.partner"].search(
            [("is_company", "=", True), ("customer_rank", ">", 0), ("active", "=", True)],
            limit=200,
        )
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
