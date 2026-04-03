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
            return results
        except Exception as e:
            _logger.warning("Neo4j unavailable (%s). Falling back to pure-Python.", e)
            return self._match_pure_python(supplier, intake, mode)

    def _match_via_neo4j(self, supplier, intake, mode: str) -> list[dict[str, Any]]:
        ICP = self.env["ir.config_parameter"].sudo()
        uri = ICP.get_param("plasticos.neo4j.uri")
        user = ICP.get_param("plasticos.neo4j.user")
        pwd = ICP.get_param("plasticos.neo4j.pass")
        if not all([uri, user, pwd]):
            raise RuntimeError("Neo4j system parameters not configured.")

        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise RuntimeError("neo4j driver not installed.") from exc

        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        mp = intake.material_profile_id
        polymer = mp.polymer or ""
        form = mp.form or ""
        resin_grade = mp.resin_grade or ""
        qty_lbs = intake.quantity_lbs or 0.0
        price_lb = intake.asking_price or 0.0
        geo_region = (intake.facility_profile_id.region or "") if intake.facility_profile_id else ""
        threshold = 0.60 if mode == "strict" else 0.35

        cypher = """
        MATCH (b:Buyer)-[s:SOLD_TO]->(p:Polymer {name: $polymer})
        WHERE b.active = true
        AND (b.form = $form OR $form = '')
        AND (b.resin_grade = $resin_grade OR $resin_grade = '')
        AND ($qty_lbs = 0 OR (b.min_qty_lbs <= $qty_lbs AND b.max_qty_lbs >= $qty_lbs))
        WITH b, s
        RETURN
          b.odoo_partner_id AS buyer_id,
          s.avg_price_per_lb AS avg_price_per_lb,
          s.relationship_score AS relationship_score,
          b.capacity_available AS capacity_available,
          b.region AS region
        ORDER BY relationship_score DESC
        LIMIT 50
        """

        with driver.session() as session:
            rows = session.run(
                cypher, polymer=polymer, form=form,
                resin_grade=resin_grade, qty_lbs=qty_lbs,
            ).data()
        driver.close()

        results = []
        for row in rows:
            score, passed, failed = self._score_neo4j_row(row, intake, geo_region, price_lb)
            if score < threshold:
                continue
            # TODO #2 FIX: typical_price from avg_price_per_lb edge property
            # (was hardcoded 0.0 for all rows)
            results.append({
                "buyer_id": row["buyer_id"],
                "total_score": score,
                "gates_passed": passed,
                "gates_total": _GATE_TOTAL,
                "gates_failed": failed,
                "typical_price": row.get("avg_price_per_lb") or 0.0,
            })

        results.sort(key=lambda r: r["total_score"], reverse=True)
        return results

    def _score_neo4j_row(self, row, intake, geo_region, price_lb):
        mp = intake.material_profile_id
        gs = {
            "polymer_match": 1.0,
            "form_match": 1.0 if not (mp and mp.form) else (1.0 if row.get("form") == mp.form else 0.0),
            "resin_grade_match": 1.0 if not (mp and mp.resin_grade) else (1.0 if row.get("resin_grade") == mp.resin_grade else 0.0),
            "quantity_range": 1.0,
            "price_range": 1.0 if price_lb == 0.0 else (
                1.0 if abs((row.get("avg_price_per_lb") or price_lb) - price_lb) / max(price_lb, 0.01) <= 0.20 else 0.5
            ),
            "geography": 1.0 if not geo_region or row.get("region") == geo_region else 0.5,
            "certification": 1.0,
            "contamination": 1.0,
            "lead_time": 1.0,
            "relationship_score": min(1.0, (row.get("relationship_score") or 0.0) / 10.0),
            "capacity_available": 1.0 if row.get("capacity_available") else 0.0,
            "active_buyer": 1.0,
        }
        total = sum(_GATE_WEIGHTS[g] * gs[g] for g in _GATE_WEIGHTS)
        passed = sum(1 for g in gs if gs[g] > 0.0)
        failed = [g for g in gs if gs[g] == 0.0]
        return round(total, 6), passed, failed

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
        if mp and mp.polymer:
            accepted = str(buyer.mapped("facility_profile_ids.accepted_polymers"))
            gs["polymer_match"] = 1.0 if mp.polymer in accepted else 0.0
        total = sum(_GATE_WEIGHTS[g] * gs[g] for g in _GATE_WEIGHTS)
        passed = sum(1 for g in gs if gs[g] > 0.0)
        failed = [g for g in gs if gs[g] == 0.0]
        return round(total, 6), passed, failed
