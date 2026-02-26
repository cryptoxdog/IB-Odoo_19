"""Neo4j graph orchestration for buyer matching.

Implements plasticos.graph.service (AbstractModel): sync Facility/MaterialProfile
nodes and run graph traversal for calculate_match_score.

Architecture:
    - services/neo4j_pool.py: Connection pooling with circuit breaker
    - services/monitoring.py: Metrics collection (timing, counters)

Public API:
    - execute_cypher_query(): Pooled + metrics, raises UserError on failure
    - _execute_cypher(): Optional/graceful, returns [] on failure (for hooks)
    - sync_facility_nodes(), sync_material_nodes(), sync_all(): Graph sync
    - calculate_match_score(): v2.0 scoring API called by plasticos.buyer.matcher
"""

import logging
import os
from datetime import datetime

from odoo import fields, models  # pyright: ignore[reportMissingImports]
from odoo.exceptions import UserError  # pyright: ignore[reportMissingImports]


def _get_form_codes():
    """Lazy load form codes to avoid import error at module load time."""
    from odoo.addons.plasticos_material_profile.form_codes import (
        EQUIPMENT_GATED_FORMS,
        PASSTHROUGH_FORMS,
    )

    return EQUIPMENT_GATED_FORMS, PASSTHROUGH_FORMS


_logger = logging.getLogger(__name__)


def _env_neo4j_uri():
    """Neo4j URI from environment (.env): NEO4J_URI or NEO4J_URL."""
    return os.environ.get("NEO4J_URI") or os.environ.get("NEO4J_URL") or ""


def _env_neo4j_user():
    return os.environ.get("NEO4J_USER", "")


def _env_neo4j_password():
    return os.environ.get("NEO4J_PASSWORD", "")


try:
    from neo4j.exceptions import Neo4jError, ServiceUnavailable  # pyright: ignore[reportMissingImports]
except ImportError:
    Neo4jError = Exception
    ServiceUnavailable = Exception


def _neo4j_pool():
    from odoo.addons.plasticos_buyer_match_engine.services import neo4j_pool  # pyright: ignore[reportMissingImports]

    return neo4j_pool.Neo4jConnectionPool


class PlasticosGraphService(models.AbstractModel):
    _name = "plasticos.graph.service"
    _description = "PlastOS Graph Engine (Neo4j buyer matching)"

    def action_test_neo4j_connection(self):
        """Test Neo4j connectivity and return status.

        Can be called from Odoo UI (button) or via RPC.
        Returns dict with connection status and details.
        """
        config = self._get_config()
        uri = config.get("uri", "")

        if not uri:
            return {
                "success": False,
                "message": "Neo4j URI not configured. Set plasticos_graph.neo4j_uri in System Parameters or NEO4J_URI env var.",
                "uri": "",
            }

        try:
            pool_cls = _neo4j_pool()
            pool = pool_cls(
                uri=uri,
                username=config.get("user", ""),
                password=config.get("password", ""),
                pool_size=config.get("pool_size", 25),
                connection_timeout=config.get("connection_timeout", 30),
            )
            healthy = pool.health_check()
            if healthy:
                return {
                    "success": True,
                    "message": f"Neo4j connection successful: {uri}",
                    "uri": uri,
                }
            else:
                return {
                    "success": False,
                    "message": f"Neo4j health check failed for: {uri}",
                    "uri": uri,
                }
        except Exception as exc:
            _logger.error("Neo4j connection test failed: %s", exc)
            return {
                "success": False,
                "message": f"Neo4j connection failed: {exc}",
                "uri": uri,
            }

    def _get_config(self):
        """Return Neo4j connection and match config.

        Uri, user, password: from System Parameters (plasticos_graph.*) with
        fallback to .env (NEO4J_URI or NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD).
        """
        ICP = self.env["ir.config_parameter"].sudo()
        uri = (ICP.get_param("plasticos_graph.neo4j_uri") or "").strip() or _env_neo4j_uri()
        user = (ICP.get_param("plasticos_graph.neo4j_user") or "").strip() or _env_neo4j_user()
        password = (ICP.get_param("plasticos_graph.neo4j_password") or "").strip() or _env_neo4j_password()

        return {
            "uri": uri,
            "user": user,
            "password": password,
            "pool_size": int(ICP.get_param("plasticos_graph.neo4j_pool_size", "25")),
            "connection_timeout": int(ICP.get_param("plasticos_graph.neo4j_connection_timeout", "30")),
            "max_lifetime": int(ICP.get_param("plasticos_graph.neo4j_max_connection_lifetime", "3600")),
            "cb_threshold": int(ICP.get_param("plasticos_graph.neo4j_cb_failure_threshold", "5")),
            "cb_timeout": int(ICP.get_param("plasticos_graph.neo4j_cb_timeout", "60")),
            "max_distance_km": float(ICP.get_param("plasticos_graph.match_geo_radius_miles", "500")) * 1.60934,
            "match_max_results": int(ICP.get_param("plasticos_graph.match_max_results", "25")),
        }

    def _get_scoring_weights(self):
        """
        Get scoring weights from system parameters or defaults.

        Returns:
            dict: {dimension: weight} for 4 scoring dimensions (spec v2.0)
                - hard_gate: Pass/fail score from Stage 1 gates
                - quality: Density/MFI range fit, contamination proximity
                - geo: Geographic proximity score
                - history: Transaction history bonus
        """
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "hard_gate": float(ICP.get_param("plasticos_graph.scoring_w1_hard", "0.50")),
            "quality": float(ICP.get_param("plasticos_graph.scoring_w2_quality", "0.15")),
            "geo": float(ICP.get_param("plasticos_graph.scoring_w3_geo", "0.25")),
            "history": float(ICP.get_param("plasticos_graph.scoring_w4_history", "0.10")),
        }

    def calculate_match_score(self, supplier_partner_id, buyer_partner_id, material_requirements):
        """
        Calculate match score between supplier and buyer using Neo4j.
        Called by the Python matcher (Stage 1) for Stage 2 scoring.

        Scoring dimensions (spec v2.0):
            - hard_gate (w1): Pass/fail from Stage 1 gates (material + volume + compliance)
            - quality (w2): Density/MFI range fit, contamination proximity
            - geo (w3): Geographic proximity score
            - history (w4): Transaction history bonus

        Args:
            supplier_partner_id: res.partner ID of supplier
            buyer_partner_id: res.partner ID of buyer
            material_requirements: dict with material specs from intake

        Returns:
            dict: {
                'total_score': float (0.0-1.0),
                'hard_gate_score': float,
                'quality_score': float,
                'geo_score': float,
                'history_score': float,
                'distance_miles': float or None
            }
        """
        weights = self._get_scoring_weights()

        query = """
        MATCH (supplier:Facility {facility_id: $supplier_id})
        MATCH (buyer:Facility {facility_id: $buyer_id})
        OPTIONAL MATCH (buyer)-[:HAS_MATERIAL]->(mat:MaterialProfile)

        // Calculate scores with gate_mode adjustment (spec v2.0: 4 dimensions)
        // Schema alignment: Material.polymer stores the polymer code (e.g., 'HDPE')
        WITH supplier, buyer, mat,
             // HARD_GATE score: Combined material + volume + compliance gates
             // This represents "did Stage 1 gates pass?" as a continuous score
             CASE
                 WHEN buyer.gate_mode = 'strict' THEN
                     CASE
                         WHEN mat.polymer = $polymer_code AND
                              (buyer.min_lot_size_lbs IS NULL OR $quantity_available >= buyer.min_lot_size_lbs)
                         THEN 1.0
                         ELSE 0.0
                     END
                 WHEN buyer.gate_mode = 'flexible' THEN
                     CASE
                         WHEN mat.polymer = $polymer_code THEN 1.0
                         WHEN mat.polymer IS NOT NULL THEN 0.7
                         ELSE 0.5
                     END
                 WHEN buyer.gate_mode = 'optimistic' THEN
                     CASE
                         WHEN mat.polymer = $polymer_code THEN 0.9
                         ELSE 0.7
                     END
                 ELSE 0.5
             END AS hard_gate_score,

             // QUALITY score: Based on material profile match (MFI, density, contamination tolerance)
             // Schema alignment: quality is derived from MaterialProfile attributes, not a separate ID
             CASE
                 WHEN mat IS NOT NULL AND mat.polymer = $polymer_code THEN 1.0
                 WHEN mat IS NOT NULL THEN 0.8
                 ELSE 0.6
             END AS quality_score,

             // GEO score: Geographic proximity (distance-based)
             CASE
                 WHEN supplier.lat IS NULL OR supplier.lon IS NULL THEN 0.5
                 WHEN buyer.lat IS NULL OR buyer.lon IS NULL THEN 0.5
                 ELSE
                   CASE
                   WHEN point.distance(
                     point({latitude: supplier.lat, longitude: supplier.lon}),
                     point({latitude: buyer.lat, longitude: buyer.lon})
                   ) / 1609.34 <= 100 THEN 1.0
                   WHEN point.distance(
                     point({latitude: supplier.lat, longitude: supplier.lon}),
                     point({latitude: buyer.lat, longitude: buyer.lon})
                   ) / 1609.34 <= 500 THEN 0.7
                   ELSE 0.4
                   END
             END AS geo_score,

             // Distance calculation (for display)
             CASE
                 WHEN supplier.lat IS NOT NULL AND buyer.lat IS NOT NULL
                 THEN point.distance(
                     point({latitude: supplier.lat, longitude: supplier.lon}),
                     point({latitude: buyer.lat, longitude: buyer.lon})
                 ) / 1609.34
                 ELSE null
             END AS distance_miles

        // Transaction history for HISTORY score
        // Schema: SOLD_TO edges link MaterialProfile→Facility (ontology v2.0)
        OPTIONAL MATCH (supplier)-[:HAS_MATERIAL]->(sm:MaterialProfile)-[tx:SOLD_TO]->(buyer)

        WITH hard_gate_score, quality_score, geo_score, distance_miles,
             CASE WHEN tx IS NOT NULL THEN 1.0 ELSE 0.0 END AS history_score,
             coalesce(tx.tx_count, 0) AS tx_count

        // Weighted total score (spec v2.0: 4 dimensions)
        WITH hard_gate_score, quality_score, geo_score, history_score, distance_miles, tx_count,
             (hard_gate_score * $w_hard_gate +
              quality_score * $w_quality +
              geo_score * $w_geo +
              history_score * $w_history) AS total_score

        RETURN
            total_score,
            hard_gate_score,
            quality_score,
            geo_score,
            history_score,
            distance_miles,
            tx_count
        """

        params = {
            "supplier_id": supplier_partner_id,
            "buyer_id": buyer_partner_id,
            # Schema alignment: use polymer_code (string like 'HDPE') for Neo4j matching
            "polymer_code": material_requirements.get("polymer_code"),
            "quantity_available": material_requirements.get("quantity_available") or 0,
            "w_hard_gate": weights["hard_gate"],
            "w_quality": weights["quality"],
            "w_geo": weights["geo"],
            "w_history": weights["history"],
        }

        try:
            rows = self._execute_cypher(query, params)
            if rows:
                return rows[0]
            return {"total_score": 0.0}
        except Exception as e:
            _logger.error("Error calculating match score: %s", e)
            return {"total_score": 0.0}

    # ═══════════════════════════════════════════════════════════════════════
    # Dual-Mode Buyer Matching (v2.0)
    # ═══════════════════════════════════════════════════════════════════════

    def match_buyers(self, intake, facility_ids, mode="strict"):
        """Run Stage 2 matching with mode-appropriate Cypher query.

        Args:
            intake: plasticos.intake record
            facility_ids: List of facility IDs from Stage 1 survivors
            mode: 'strict' or 'relaxed'

        Returns:
            List of match results with scores
        """
        params = self._intake_to_match_params(intake)
        params["facility_ids"] = facility_ids

        if mode == "strict":
            query = self._build_strict_query()
            run_id = "strict_v1"
        else:
            query = self._build_relaxed_query()
            run_id = "relaxed_v1"

        rows = self._execute_cypher(query, params)

        # Persist results with run_id
        self._persist_match_results(intake, rows, run_id=run_id)

        return rows

    def _intake_to_match_params(self, intake):
        """Convert intake record to Cypher query parameters."""
        return {
            "polymer": intake.polymer_id.code if intake.polymer_id else None,
            "density": intake.density_value or None,
            "mfi": intake.mfi_value or None,
            "contamination_pct": intake.contamination_pct or 0.0,
            "moisture_pct": intake.moisture_pct or 0.0,
            "has_metal": intake.has_metal or False,
            "has_fr": intake.has_fr or False,
            "form": intake.form_id.code if intake.form_id else None,
            "quantity_lbs": intake.quantity_per_load_lbs or 0,
            "food_grade_required": intake.origin_sector == "food",
            "medical_grade_required": intake.origin_sector == "medical",
            "filler_pct": intake.filler_pct or 0.0,
        }

    @staticmethod
    def _build_form_gate_where():
        """Generate Cypher WHERE clause for form-equipment gate from canonical registry.

        Derived from ``EQUIPMENT_GATED_FORMS`` and ``PASSTHROUGH_FORMS`` in
        ``plasticos_material_profile.form_codes`` — the single source of truth.
        """
        equipment_gated_forms, passthrough_forms = _get_form_codes()
        lines = ["$form IS NULL"]
        for form_code, condition in equipment_gated_forms.items():
            lines.append(f"($form = '{form_code}' AND {condition} = true)")
        passthrough_list = ", ".join(f"'{c}'" for c in passthrough_forms)
        lines.append(f"($form IN [{passthrough_list}])")
        return "\n            OR ".join(lines)

    @staticmethod
    def _build_form_gate_case():
        """Generate Cypher CASE expression for form-equipment scoring from canonical registry.

        Returns CASE block where equipment-gated forms score 1.0 only if
        equipment is present, passthrough forms always score 1.0, and
        unknown forms get 0.3 penalty.
        """
        equipment_gated_forms, passthrough_forms = _get_form_codes()
        lines = ["WHEN $form IS NULL THEN 1.0"]
        for form_code, condition in equipment_gated_forms.items():
            lines.append(f"WHEN $form = '{form_code}' AND {condition} = true THEN 1.0")
        passthrough_list = ", ".join(f"'{c}'" for c in passthrough_forms)
        lines.append(f"WHEN $form IN [{passthrough_list}] THEN 1.0")
        lines.append("ELSE 0.3")
        return "\n                ".join(lines)

    def _build_strict_query(self):
        """Build Cypher query with ALL 14 gates as hard WHERE predicates."""
        form_gate_where = self._build_form_gate_where()
        return f"""
        // Stage 2 STRICT: All 14 gates as hard exclusions
        MATCH (f:Facility)-[:HAS_MATERIAL]->(m:MaterialProfile)
        WHERE f.facility_id IN $facility_ids

        // Gate 1: Polymer (HARD)
        AND m.polymer = $polymer

        // Gate 2: Density range (HARD)
        AND (m.min_density IS NULL OR m.min_density <= $density)
        AND (m.max_density IS NULL OR m.max_density >= $density)

        // Gate 3: MFI range (HARD)
        AND (m.mfi_min IS NULL OR m.mfi_min <= $mfi)
        AND (m.mfi_max IS NULL OR m.mfi_max >= $mfi)

        // Gate 4: MFI-Process compatibility (HARD - physics constraint)
        AND (
            f.process_type IS NULL
            OR (f.process_type = 'injection' AND $mfi >= 10)
            OR (f.process_type = 'extrusion' AND $mfi <= 20)
            OR (f.process_type = 'blow_mold' AND $mfi >= 0.5 AND $mfi <= 10)
            OR (f.process_type = 'film_blown' AND $mfi <= 5)
            OR (f.process_type = 'film_cast' AND $mfi <= 5)
            OR (f.process_type = 'thermoform' AND $mfi >= 1 AND $mfi <= 12)
            OR (f.process_type = 'rotomold' AND $mfi >= 2 AND $mfi <= 10)
            OR f.process_type IN ['compounding', 'other']
        )

        // Gate 5: Contamination tolerance (HARD)
        AND (m.contamination_tolerance IS NULL OR m.contamination_tolerance >= $contamination_pct)

        // Gate 6: Moisture tolerance (HARD)
        AND (m.moisture_tolerance IS NULL OR m.moisture_tolerance >= $moisture_pct)

        // Gate 7: Metal removal capability (HARD if material has metal)
        AND (NOT $has_metal OR f.can_remove_metal = true)

        // Gate 8: FR filtering capability (HARD if material has FR)
        AND (NOT $has_fr OR f.can_filter_fr = true)

        // Gate 9: Wash line/dryer capability (HARD if moisture present)
        AND ($moisture_pct <= 0.5 OR f.has_wash_line = true)

        // Gate 10: Form-Equipment compatibility (HARD)
        // Generated from plasticos_material_profile.form_codes canonical registry
        AND (
            {form_gate_where}
        )

        // Gate 11: PVC tolerance (HARD - based on contamination notes)
        AND (m.pvc_tolerance IS NULL OR m.pvc_tolerance = true)

        // Gate 12: Filler tolerance (HARD)
        AND ($filler_pct <= 0 OR f.accepts_filled_materials = true)

        // Gate 13: Lot size (HARD)
        AND (f.min_lot_size_lbs IS NULL OR f.min_lot_size_lbs <= $quantity_lbs)
        AND (f.max_lot_size_lbs IS NULL OR f.max_lot_size_lbs >= $quantity_lbs)

        // Gate 14: Certifications (HARD)
        AND (NOT $food_grade_required OR f.food_grade_certified = true)
        AND (NOT $medical_grade_required OR f.medical_grade_capable = true)

        RETURN
            f.facility_id AS facility_id,
            f.name AS facility_name,
            m.material_id AS material_id,
            100.0 AS total_score,
            'strict' AS match_mode
        ORDER BY f.name
        """

    def _build_relaxed_query(self):
        """Build Cypher query with ONLY polymer as hard gate, others as soft scoring signals."""
        form_gate_case = self._build_form_gate_case()
        return f"""
        // Stage 2 RELAXED: Only polymer is hard, all others are multiplicative penalties
        MATCH (f:Facility)-[:HAS_MATERIAL]->(m:MaterialProfile)
        WHERE f.facility_id IN $facility_ids

        // ONLY HARD GATE: Polymer
        AND m.polymer = $polymer

        // Calculate multiplicative penalty factors for soft gates
        WITH f, m,
            // Density (x0.3 penalty if out of range)
            CASE
                WHEN m.min_density IS NULL AND m.max_density IS NULL THEN 1.0
                WHEN (m.min_density IS NULL OR m.min_density <= $density)
                     AND (m.max_density IS NULL OR m.max_density >= $density) THEN 1.0
                ELSE 0.3
            END AS density_mult,

            // MFI range (x0.3 penalty)
            CASE
                WHEN m.mfi_min IS NULL AND m.mfi_max IS NULL THEN 1.0
                WHEN (m.mfi_min IS NULL OR m.mfi_min <= $mfi)
                     AND (m.mfi_max IS NULL OR m.mfi_max >= $mfi) THEN 1.0
                ELSE 0.3
            END AS mfi_mult,

            // MFI-Process compatibility (x0.1 HEAVY penalty - physics constraint)
            CASE
                WHEN f.process_type IS NULL THEN 1.0
                WHEN f.process_type = 'injection' AND $mfi >= 10 THEN 1.0
                WHEN f.process_type = 'extrusion' AND $mfi <= 20 THEN 1.0
                WHEN f.process_type = 'blow_mold' AND $mfi >= 0.5 AND $mfi <= 10 THEN 1.0
                WHEN f.process_type = 'film_blown' AND $mfi <= 5 THEN 1.0
                WHEN f.process_type = 'film_cast' AND $mfi <= 5 THEN 1.0
                WHEN f.process_type = 'thermoform' AND $mfi >= 1 AND $mfi <= 12 THEN 1.0
                WHEN f.process_type = 'rotomold' AND $mfi >= 2 AND $mfi <= 10 THEN 1.0
                WHEN f.process_type IN ['compounding', 'other'] THEN 1.0
                ELSE 0.1
            END AS mfi_process_mult,

            // Contamination (x0.3 penalty)
            CASE
                WHEN m.contamination_tolerance IS NULL THEN 1.0
                WHEN m.contamination_tolerance >= $contamination_pct THEN 1.0
                ELSE 0.3
            END AS contamination_mult,

            // Moisture (x0.3 penalty)
            CASE
                WHEN m.moisture_tolerance IS NULL THEN 1.0
                WHEN m.moisture_tolerance >= $moisture_pct THEN 1.0
                ELSE 0.3
            END AS moisture_mult,

            // Metal removal (x0.5 penalty)
            CASE
                WHEN NOT $has_metal THEN 1.0
                WHEN f.can_remove_metal = true THEN 1.0
                ELSE 0.5
            END AS metal_mult,

            // FR filtering (x0.5 penalty)
            CASE
                WHEN NOT $has_fr THEN 1.0
                WHEN f.can_filter_fr = true THEN 1.0
                ELSE 0.5
            END AS fr_mult,

            // Wash line (x0.5 penalty)
            CASE
                WHEN $moisture_pct <= 0.5 THEN 1.0
                WHEN f.has_wash_line = true THEN 1.0
                ELSE 0.5
            END AS wash_mult,

            // Form-Equipment (x0.3 penalty)
            // Generated from plasticos_material_profile.form_codes canonical registry
            CASE
                {form_gate_case}
            END AS form_mult,

            // PVC/Filler (x0.3 penalty)
            CASE
                WHEN $filler_pct <= 0 THEN 1.0
                WHEN f.accepts_filled_materials = true THEN 1.0
                ELSE 0.3
            END AS filler_mult,

            // Lot size (x0.5 penalty)
            CASE
                WHEN f.min_lot_size_lbs IS NULL AND f.max_lot_size_lbs IS NULL THEN 1.0
                WHEN (f.min_lot_size_lbs IS NULL OR f.min_lot_size_lbs <= $quantity_lbs)
                     AND (f.max_lot_size_lbs IS NULL OR f.max_lot_size_lbs >= $quantity_lbs) THEN 1.0
                ELSE 0.5
            END AS lot_mult,

            // Certifications (x0.5 penalty)
            CASE
                WHEN NOT $food_grade_required AND NOT $medical_grade_required THEN 1.0
                WHEN $food_grade_required AND f.food_grade_certified = true THEN 1.0
                WHEN $medical_grade_required AND f.medical_grade_capable = true THEN 1.0
                ELSE 0.5
            END AS cert_mult

        // Calculate final multiplicative score
        WITH f, m,
            density_mult, mfi_mult, mfi_process_mult, contamination_mult, moisture_mult,
            metal_mult, fr_mult, wash_mult, form_mult, filler_mult, lot_mult, cert_mult,
            100.0 * density_mult * mfi_mult * mfi_process_mult * contamination_mult
                  * moisture_mult * metal_mult * fr_mult * wash_mult
                  * form_mult * filler_mult * lot_mult * cert_mult AS total_score

        RETURN
            f.facility_id AS facility_id,
            f.name AS facility_name,
            m.material_id AS material_id,
            total_score,
            'relaxed' AS match_mode,
            density_mult, mfi_mult, mfi_process_mult, contamination_mult, moisture_mult,
            metal_mult, fr_mult, wash_mult, form_mult, filler_mult, lot_mult, cert_mult
        ORDER BY total_score DESC
        """

    def _persist_match_results(self, intake, rows, run_id="unknown"):
        """Persist match results to plasticos.match.result with run_id tagging.

        Field mapping (graph row -> match.result):
            facility_id  -> buyer_facility_id  (res.partner Many2one)
            total_score  -> score              (Float)
            profile_id   -> facility_profile_id (plasticos.facility.profile Many2one)
        """
        MatchResult = self.env["plasticos.match.result"]

        for row in rows:
            try:
                # facility_id from Cypher = res.partner.id (set in sync)
                partner_id = row.get("facility_id")
                buyer_partner_id = None
                buyer_facility_id = None
                facility_profile_id = None
                if partner_id:
                    partner = self.env["res.partner"].browse(partner_id)
                    if partner.exists():
                        # buyer_partner_id = company (parent) or partner itself
                        buyer_partner_id = partner.parent_id.id or partner.id
                        buyer_facility_id = partner.id
                    # Look up first matching profile for this partner
                    profile = self.env["plasticos.facility.profile"].search(
                        [("partner_id", "=", partner_id), ("active", "=", True)], limit=1
                    )
                    if profile:
                        facility_profile_id = profile.id

                MatchResult.create(
                    {
                        "intake_id": intake.id,
                        "buyer_partner_id": buyer_partner_id,
                        "buyer_facility_id": buyer_facility_id,
                        "facility_profile_id": facility_profile_id,
                        "score": row.get("total_score", 0.0),
                        "score_breakdown": row.get("score_breakdown"),
                        "run_id": run_id,
                        "model_version": "2.0.0",
                        "timestamp": datetime.now(),
                    }
                )
            except Exception as e:
                _logger.warning("Failed to persist match result: %s", e)

    def _get_pool(self):
        """Return shared Neo4jConnectionPool; raises UserError if Neo4j not configured."""
        cfg = self._get_config()
        uri, user, password = cfg["uri"], cfg["user"], cfg["password"]
        if not uri or not user or not password:
            raise UserError(
                "Neo4j connection is not configured. Set:\n"
                "- plasticos_graph.neo4j_uri\n"
                "- plasticos_graph.neo4j_user\n"
                "- plasticos_graph.neo4j_password"
            )
        pool_class = _neo4j_pool()
        return pool_class(
            uri,
            user,
            password,
            pool_size=cfg["pool_size"],
            connection_timeout=cfg["connection_timeout"],
            max_lifetime=cfg["max_lifetime"],
            circuit_breaker_threshold=cfg["cb_threshold"],
            circuit_breaker_timeout=cfg["cb_timeout"],
        )

    def execute_cypher_query(self, query, params=None, metadata=None):
        """Execute a Cypher query with shared pool + metrics.

        This is the advanced pooled+metrics version from doc/execute_cypher_pooled.md.

        :param query: Cypher query string.
        :param params: Optional dict of parameters.
        :param metadata: Optional dict (e.g. {"name": "sync_facility"}).
        :return: list of dict rows from Neo4j (record.data() per row).
        """
        from ..services.monitoring import get_metrics  # Relative import for pyright

        params = params or {}
        metadata = metadata or {}
        op_name = metadata.get("name", "neo4j.query")

        metrics = get_metrics()
        pool = self._get_pool()

        _logger.info("Neo4j query start: %s | metadata=%s", op_name, metadata)

        try:
            with metrics.measure(op_name):
                with pool.session() as session:
                    result = session.run(query, params)
                    rows = [record.data() for record in result]

            metrics.increment(f"{op_name}.rows", len(rows))
            _logger.info("Neo4j query ok: %s | rows=%d", op_name, len(rows))
            return rows

        except ServiceUnavailable as exc:
            metrics.increment(f"{op_name}.service_unavailable")
            _logger.error(
                "Neo4j service unavailable: %s | metadata=%s",
                exc,
                metadata,
                exc_info=True,
            )
            raise UserError(
                "Neo4j service is unavailable. Please try again later or contact your administrator."
            ) from exc

        except Neo4jError as exc:
            metrics.increment(f"{op_name}.neo4j_error")
            _logger.error(
                "Neo4j error: %s | metadata=%s",
                exc,
                metadata,
                exc_info=True,
            )
            raise UserError("Neo4j query failed:\n{}".format(getattr(exc, "message", str(exc)))) from exc

        except Exception as exc:
            metrics.increment(f"{op_name}.unexpected_error")
            _logger.exception(
                "Unexpected error while executing Neo4j query | metadata=%s",
                metadata,
            )
            raise UserError("Unexpected error while communicating with Neo4j. Check Odoo logs for details.") from exc

    def _get_driver(self):
        """Return pool or None when Neo4j is optional (hooks/sync); no UserError."""
        cfg = self._get_config()
        if not cfg.get("password"):
            return None
        try:
            pool_class = _neo4j_pool()
            return pool_class(
                cfg["uri"],
                cfg["user"],
                cfg["password"],
                pool_size=cfg.get("pool_size", 10),
                connection_timeout=cfg.get("connection_timeout", 15),
                max_lifetime=cfg.get("max_lifetime", 3600),
                circuit_breaker_threshold=cfg.get("cb_threshold", 5),
                circuit_breaker_timeout=cfg.get("cb_timeout", 60),
            )
        except Exception as exc:
            _logger.warning("Neo4j pool not available: %s", exc)
            return None

    def _execute_cypher(self, query, params=None, metadata=None):
        """Execute Cypher when Neo4j is optional; returns [] on missing config or failure."""
        params = params or {}
        driver = self._get_driver()
        if not driver or not getattr(driver, "driver", None) or not driver.driver:
            return []
        try:
            with driver.session() as session:
                result = session.run(query, params)
                return [record.data() for record in result]
        except Exception as exc:
            _logger.warning("Cypher execution failed: %s", exc)
            return []

    def initialize_schema(self):
        driver = self._get_driver()
        if not driver or not driver.driver:
            return
        constraints = [
            "CREATE CONSTRAINT facility_id IF NOT EXISTS FOR (f:Facility) REQUIRE f.facility_id IS UNIQUE",
            "CREATE CONSTRAINT material_id IF NOT EXISTS FOR (m:MaterialProfile) REQUIRE m.material_id IS UNIQUE",
            # Taxonomy node uniqueness constraints
            "CREATE CONSTRAINT polymer_code IF NOT EXISTS FOR (p:Polymer) REQUIRE p.code IS UNIQUE",
            "CREATE CONSTRAINT form_code IF NOT EXISTS FOR (f:MaterialForm) REQUIRE f.code IS UNIQUE",
            "CREATE CONSTRAINT process_code IF NOT EXISTS FOR (p:ProcessType) REQUIRE p.code IS UNIQUE",
            "CREATE CONSTRAINT color_code IF NOT EXISTS FOR (c:MaterialColor) REQUIRE c.code IS UNIQUE",
            "CREATE CONSTRAINT filler_code IF NOT EXISTS FOR (f:FillerType) REQUIRE f.code IS UNIQUE",
            "CREATE CONSTRAINT source_code IF NOT EXISTS FOR (s:SourceType) REQUIRE s.code IS UNIQUE",
            "CREATE CONSTRAINT equipment_code IF NOT EXISTS FOR (e:EquipmentType) REQUIRE e.code IS UNIQUE",
            "CREATE CONSTRAINT market_code IF NOT EXISTS FOR (m:Market) REQUIRE m.code IS UNIQUE",
        ]
        for cypher in constraints:
            try:
                self._execute_cypher(cypher)
            except Exception as exc:
                _logger.debug("Schema init step skipped: %s", exc)

    def _build_facility_payloads(self):
        """Build Facility node payloads including geo location.

        Queries partners with facility profiles and aggregates capabilities
        across all profiles for each partner.
        """
        # Find all partners that have facility profiles
        partners = self.env["res.partner"].search(
            [
                ("facility_profile_ids", "!=", False),
            ]
        )

        payloads = []
        for partner in partners:
            profiles = partner.facility_profile_ids.filtered(lambda fp: fp.active)
            if not profiles:
                continue

            # Aggregate capabilities across all facility profiles for this partner
            # Equipment flags: True if ANY profile has the capability
            payloads.append(
                {
                    "facility_id": partner.id,
                    "partner_id": partner.id,
                    "name": partner.name or "",
                    "customer_rank": partner.customer_rank or 0,
                    "supplier_rank": partner.supplier_rank or 0,
                    # Gate mode from partner type (for v2.0 matching)
                    "gate_mode": partner.partner_type_id.gate_mode if partner.partner_type_id else "flexible",
                    "lat": partner.partner_latitude or None,
                    "lon": partner.partner_longitude or None,
                    "city": partner.city or None,
                    "state": partner.state_id.code if partner.state_id else None,
                    "country": partner.country_id.code if partner.country_id else None,
                    # Partner-level role (broker, processor, etc.)
                    "facility_role": partner.x_facility_role or None,
                    # Contamination handling capabilities
                    "can_remove_metal": any(getattr(fp, "can_remove_metal", False) for fp in profiles),
                    "can_filter_fr": any(getattr(fp, "can_filter_fr", False) for fp in profiles),
                    "can_reduce_moisture": any(getattr(fp, "can_reduce_moisture", False) for fp in profiles),
                    # Equipment flags for form-equipment compatibility
                    "has_shredder": any(getattr(fp, "has_shredder", False) for fp in profiles),
                    "has_granulator": any(getattr(fp, "has_granulator", False) for fp in profiles),
                    "has_wash_line": any(getattr(fp, "has_wash_line", False) for fp in profiles),
                    "has_extruder": any(getattr(fp, "has_extruder", False) for fp in profiles),
                    "has_sorting_line": any(getattr(fp, "has_sorting_line", False) for fp in profiles),
                    # Form handling capabilities
                    "handles_regrind": any(getattr(fp, "handles_regrind", False) for fp in profiles),
                    "handles_flake": any(getattr(fp, "handles_flake", False) for fp in profiles),
                    "handles_rollstock": any(getattr(fp, "handles_rollstock", False) for fp in profiles),
                    # Certifications
                    "food_grade_certified": any(getattr(fp, "food_grade_certified", False) for fp in profiles),
                    "medical_grade_capable": any(getattr(fp, "medical_grade_capable", False) for fp in profiles),
                    # Process type (first non-null from profiles)
                    "process_type": next(
                        (fp.process_type for fp in profiles if fp.process_type),
                        None,
                    ),
                    # Application class (first non-null from profiles)
                    "application_class": next(
                        (fp.application_class for fp in profiles if getattr(fp, "application_class", None)),
                        None,
                    ),
                    # Filler acceptance
                    "accepts_filled_materials": any(getattr(fp, "accepts_filled_materials", False) for fp in profiles),
                    # Lot size constraints
                    "min_lot_size_lbs": min(
                        (fp.min_lot_size_lbs for fp in profiles if fp.min_lot_size_lbs),
                        default=None,
                    ),
                    "max_lot_size_lbs": max(
                        (fp.max_lot_size_lbs for fp in profiles if fp.max_lot_size_lbs),
                        default=None,
                    ),
                }
            )
        return payloads

    def _build_material_payloads(self):
        Material = self.env["plasticos.material.profile"].search([("active", "=", True)])
        payloads = []
        for mp in Material:
            payloads.append(
                {
                    "material_id": mp.id,
                    "facility_id": mp.partner_id.id,
                    "polymer": mp.polymer_id.code if mp.polymer_id else (mp.polymer or ""),
                    "form": mp.form_id.code if mp.form_id else (getattr(mp, "form", None) or ""),
                    "color": getattr(mp, "color", None) or None,
                    "min_density": getattr(mp, "min_density", None) or None,
                    "max_density": getattr(mp, "max_density", None) or None,
                    "contamination_tolerance": getattr(mp, "contamination_tolerance", None)
                    or getattr(mp, "contamination_tolerance_pct", None),
                    "moisture_tolerance": getattr(mp, "moisture_tolerance", None)
                    or getattr(mp, "moisture_tolerance_pct", None),
                    "mfi": getattr(mp, "melt_flow_index", None) or None,
                    "mfi_min": getattr(mp, "melt_index_min", None) or None,
                    "mfi_max": getattr(mp, "melt_index_max", None) or None,
                }
            )
        return payloads

    def sync_facility_nodes(self, trigger="manual"):
        """Upsert Facility nodes with geo location as Neo4j point."""
        payloads = self._build_facility_payloads()
        if not payloads:
            self._create_sync_log("facility", "success", {"records_processed": 0}, None)
            return
        query = """
        UNWIND $facilities AS f
        MERGE (fac:Facility {facility_id: f.facility_id})
        ON CREATE SET
            fac.partner_id        = f.partner_id,
            fac.name              = f.name,
            fac.customer_rank     = coalesce(f.customer_rank, 0),
            fac.supplier_rank     = coalesce(f.supplier_rank, 0),
            fac.gate_mode         = coalesce(f.gate_mode, 'flexible'),
            fac.facility_role     = f.facility_role,
            // Contamination handling
            fac.can_remove_metal  = coalesce(f.can_remove_metal, false),
            fac.can_filter_fr     = coalesce(f.can_filter_fr, false),
            fac.can_reduce_moisture = coalesce(f.can_reduce_moisture, false),
            // Equipment flags
            fac.has_shredder      = coalesce(f.has_shredder, false),
            fac.has_granulator    = coalesce(f.has_granulator, false),
            fac.has_wash_line     = coalesce(f.has_wash_line, false),
            fac.has_extruder      = coalesce(f.has_extruder, false),
            fac.has_sorting_line  = coalesce(f.has_sorting_line, false),
            // Form handling
            fac.handles_regrind   = coalesce(f.handles_regrind, false),
            fac.handles_flake     = coalesce(f.handles_flake, false),
            fac.handles_rollstock = coalesce(f.handles_rollstock, false),
            // Certifications
            fac.food_grade_certified  = coalesce(f.food_grade_certified, false),
            fac.medical_grade_capable = coalesce(f.medical_grade_capable, false),
            // Process type
            fac.process_type      = f.process_type,
            // Application class and filler acceptance
            fac.application_class = f.application_class,
            fac.accepts_filled_materials = coalesce(f.accepts_filled_materials, false),
            // Lot size constraints
            fac.min_lot_size_lbs  = f.min_lot_size_lbs,
            fac.max_lot_size_lbs  = f.max_lot_size_lbs,
            // Location (lat/lon as scalar props for scoring queries)
            fac.lat               = f.lat,
            fac.lon               = f.lon,
            fac.city              = f.city,
            fac.state             = f.state,
            fac.country           = f.country,
            fac.created_at_utc    = datetime(),
            fac.updated_at_utc    = datetime()
        ON MATCH SET
            fac.partner_id        = f.partner_id,
            fac.name              = f.name,
            fac.customer_rank     = coalesce(f.customer_rank, fac.customer_rank),
            fac.supplier_rank     = coalesce(f.supplier_rank, fac.supplier_rank),
            fac.gate_mode         = coalesce(f.gate_mode, fac.gate_mode),
            fac.facility_role     = f.facility_role,
            // Contamination handling
            fac.can_remove_metal  = coalesce(f.can_remove_metal, fac.can_remove_metal),
            fac.can_filter_fr     = coalesce(f.can_filter_fr, fac.can_filter_fr),
            fac.can_reduce_moisture = coalesce(f.can_reduce_moisture, fac.can_reduce_moisture),
            // Equipment flags
            fac.has_shredder      = coalesce(f.has_shredder, fac.has_shredder),
            fac.has_granulator    = coalesce(f.has_granulator, fac.has_granulator),
            fac.has_wash_line     = coalesce(f.has_wash_line, fac.has_wash_line),
            fac.has_extruder      = coalesce(f.has_extruder, fac.has_extruder),
            fac.has_sorting_line  = coalesce(f.has_sorting_line, fac.has_sorting_line),
            // Form handling
            fac.handles_regrind   = coalesce(f.handles_regrind, fac.handles_regrind),
            fac.handles_flake     = coalesce(f.handles_flake, fac.handles_flake),
            fac.handles_rollstock = coalesce(f.handles_rollstock, fac.handles_rollstock),
            // Certifications
            fac.food_grade_certified  = coalesce(f.food_grade_certified, fac.food_grade_certified),
            fac.medical_grade_capable = coalesce(f.medical_grade_capable, fac.medical_grade_capable),
            // Process type
            fac.process_type      = f.process_type,
            // Application class and filler acceptance
            fac.application_class = f.application_class,
            fac.accepts_filled_materials = coalesce(f.accepts_filled_materials, fac.accepts_filled_materials),
            // Lot size constraints
            fac.min_lot_size_lbs  = f.min_lot_size_lbs,
            fac.max_lot_size_lbs  = f.max_lot_size_lbs,
            // Location (lat/lon as scalar props for scoring queries)
            fac.lat               = f.lat,
            fac.lon               = f.lon,
            fac.city              = f.city,
            fac.state             = f.state,
            fac.country           = f.country,
            fac.updated_at_utc    = datetime()
        WITH fac, f
        // Set geo location as Neo4j point if lat/lon provided
        CALL {
            WITH fac, f
            WHERE f.lat IS NOT NULL AND f.lon IS NOT NULL
            SET fac.location = point({
                latitude:  toFloat(f.lat),
                longitude: toFloat(f.lon)
            })
            RETURN fac AS updated_fac
        }
        RETURN count(fac) AS n
        """
        try:
            rows = self._execute_cypher(query, {"facilities": payloads})
            n = (rows[0].get("n", 0) if rows else 0) or len(payloads)
            self._create_sync_log("facility", "success", {"records_processed": n, "trigger": trigger}, None)
        except Exception as exc:
            self._create_sync_log("facility", "failed", None, str(exc))

    def sync_material_nodes(self, trigger="manual"):
        payloads = self._build_material_payloads()
        if not payloads:
            self._create_sync_log("material", "success", {"records_processed": 0}, None)
            return
        query = """
        UNWIND $materials AS m
        MERGE (mat:MaterialProfile {material_id: m.material_id})
        ON CREATE SET
            mat.facility_id = m.facility_id, mat.polymer = m.polymer, mat.form = m.form,
            mat.color = m.color, mat.min_density = m.min_density, mat.max_density = m.max_density,
            mat.contamination_tolerance = m.contamination_tolerance, mat.moisture_tolerance = m.moisture_tolerance,
            mat.mfi = m.mfi, mat.mfi_min = m.mfi_min, mat.mfi_max = m.mfi_max,
            mat.created_at_utc = datetime(), mat.updated_at_utc = datetime()
        ON MATCH SET
            mat.facility_id = m.facility_id, mat.polymer = m.polymer, mat.form = m.form,
            mat.color = m.color, mat.min_density = m.min_density, mat.max_density = m.max_density,
            mat.contamination_tolerance = m.contamination_tolerance, mat.moisture_tolerance = m.moisture_tolerance,
            mat.mfi = m.mfi, mat.mfi_min = m.mfi_min, mat.mfi_max = m.mfi_max,
            mat.updated_at_utc = datetime()
        WITH mat, m
        MATCH (fac:Facility {facility_id: m.facility_id})
        MERGE (fac)-[:HAS_MATERIAL]->(mat)
        RETURN count(mat) AS n
        """
        try:
            rows = self._execute_cypher(query, {"materials": payloads})
            n = (rows[0].get("n", 0) if rows else 0) or len(payloads)
            self._create_sync_log("material", "success", {"records_processed": n, "trigger": trigger}, None)
        except Exception as exc:
            self._create_sync_log("material", "failed", None, str(exc))

    def sync_all(self, trigger="manual"):
        """Full graph topology sync: schema, nodes, taxonomy, edges, exclusions."""
        self.initialize_schema()
        # Phase 1: Core entity nodes
        self.sync_facility_nodes(trigger=trigger)
        self.sync_material_nodes(trigger=trigger)
        # Phase 2: Taxonomy nodes (must precede edge creation)
        self.sync_taxonomy_nodes(trigger=trigger)
        # Phase 3: Facility capability edges
        self.sync_facility_edges(trigger=trigger)
        # Phase 4: Material classification edges
        self.sync_material_edges(trigger=trigger)
        # Phase 5: Transaction history edges
        self.sync_transaction_edges(trigger=trigger)
        # Phase 6: Exclusion negative-signal edges
        self.sync_exclusion_edges(trigger=trigger)
        self._create_sync_log("full", "success", {"trigger": trigger}, None)

    # ═════════════════════════════════════════════════════════
    # Nightly Cron Entry Point
    # ═════════════════════════════════════════════════════════
    def _cron_nightly_graph_sync(self):
        """Nightly cron: full graph topology sync.

        Acquires advisory lock to prevent concurrent runs.
        """
        self.env.cr.execute(  # cron-sudo-justification: system-level graph sync
            "SELECT pg_try_advisory_lock(hashtext(%s))",
            ["plasticos_buyer_match_engine.cron_nightly_graph_sync"],
        )
        if not self.env.cr.fetchone()[0]:
            _logger.info("Nightly graph sync skipped: advisory lock held.")
            return "Skipped: lock held"
        try:
            self.sudo().sync_all(trigger="nightly_cron")  # cron-sudo-justification: system cron needs full access
            return "Nightly graph sync completed."
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))",
                ["plasticos_buyer_match_engine.cron_nightly_graph_sync"],
            )

    # ═════════════════════════════════════════════════════════
    # Phase 2: Taxonomy Node Sync
    # ═════════════════════════════════════════════════════════
    def sync_taxonomy_nodes(self, trigger="manual"):
        """Upsert all taxonomy master data as first-class Neo4j nodes.

        Taxonomy nodes: Polymer, MaterialForm, ProcessType, MaterialColor,
        FillerType, SourceType, EquipmentType, Market (state/region).
        """
        total = 0
        total += self._sync_polymer_nodes()
        total += self._sync_material_form_nodes()
        total += self._sync_process_type_nodes()
        total += self._sync_material_color_nodes()
        total += self._sync_filler_type_nodes()
        total += self._sync_source_type_nodes()
        total += self._sync_equipment_type_nodes()
        total += self._sync_market_nodes()
        self._create_sync_log("taxonomy", "success", {"records_processed": total, "trigger": trigger}, None)

    def _sync_polymer_nodes(self) -> int:
        """Upsert Polymer taxonomy nodes from plasticos.polymer."""
        if "plasticos.polymer" not in self.env:
            return 0
        records = self.env["plasticos.polymer"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [
            {
                "code": r.code,
                "name": r.name or r.code,
                "full_name": r.full_name or "",
                "category": r.category or "commodity",
                "resin_id_code": r.resin_id_code or "",
            }
            for r in records
        ]
        query = """
        UNWIND $nodes AS n
        MERGE (p:Polymer {code: n.code})
        SET p.name = n.name,
            p.full_name = n.full_name,
            p.category = n.category,
            p.resin_id_code = n.resin_id_code,
            p.updated_at_utc = datetime()
        RETURN count(p) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("Polymer taxonomy sync failed: %s", exc)
            return 0

    def _sync_material_form_nodes(self) -> int:
        """Upsert MaterialForm taxonomy nodes from plasticos.material.form."""
        if "plasticos.material.form" not in self.env:
            return 0
        records = self.env["plasticos.material.form"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [{"code": r.code, "name": r.name or r.code} for r in records]
        query = """
        UNWIND $nodes AS n
        MERGE (f:MaterialForm {code: n.code})
        SET f.name = n.name, f.updated_at_utc = datetime()
        RETURN count(f) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("MaterialForm taxonomy sync failed: %s", exc)
            return 0

    def _sync_process_type_nodes(self) -> int:
        """Upsert ProcessType taxonomy nodes from plasticos.process.type."""
        if "plasticos.process.type" not in self.env:
            return 0
        records = self.env["plasticos.process.type"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [{"code": r.code, "name": r.name or r.code} for r in records]
        query = """
        UNWIND $nodes AS n
        MERGE (p:ProcessType {code: n.code})
        SET p.name = n.name, p.updated_at_utc = datetime()
        RETURN count(p) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("ProcessType taxonomy sync failed: %s", exc)
            return 0

    def _sync_material_color_nodes(self) -> int:
        """Upsert MaterialColor taxonomy nodes from plasticos.material.color."""
        if "plasticos.material.color" not in self.env:
            return 0
        records = self.env["plasticos.material.color"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [{"code": r.code, "name": r.name or r.code, "hex_code": r.hex_code or ""} for r in records]
        query = """
        UNWIND $nodes AS n
        MERGE (c:MaterialColor {code: n.code})
        SET c.name = n.name, c.hex_code = n.hex_code, c.updated_at_utc = datetime()
        RETURN count(c) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("MaterialColor taxonomy sync failed: %s", exc)
            return 0

    def _sync_filler_type_nodes(self) -> int:
        """Upsert FillerType taxonomy nodes from plasticos.filler.type."""
        if "plasticos.filler.type" not in self.env:
            return 0
        records = self.env["plasticos.filler.type"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [{"code": r.code, "name": r.name or r.code} for r in records]
        query = """
        UNWIND $nodes AS n
        MERGE (f:FillerType {code: n.code})
        SET f.name = n.name, f.updated_at_utc = datetime()
        RETURN count(f) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("FillerType taxonomy sync failed: %s", exc)
            return 0

    def _sync_source_type_nodes(self) -> int:
        """Upsert SourceType taxonomy nodes from plasticos.source.type."""
        if "plasticos.source.type" not in self.env:
            return 0
        records = self.env["plasticos.source.type"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [{"code": r.code, "name": r.name or r.code} for r in records]
        query = """
        UNWIND $nodes AS n
        MERGE (s:SourceType {code: n.code})
        SET s.name = n.name, s.updated_at_utc = datetime()
        RETURN count(s) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("SourceType taxonomy sync failed: %s", exc)
            return 0

    def _sync_equipment_type_nodes(self) -> int:
        """Upsert EquipmentType taxonomy nodes from plasticos.equipment.type."""
        if "plasticos.equipment.type" not in self.env:
            return 0
        records = self.env["plasticos.equipment.type"].search(["&", ("active", "=", True), ("code", "!=", False)])
        if not records:
            return 0
        payloads = [{"code": r.code, "name": r.name or r.code, "category": r.category or "equipment"} for r in records]
        query = """
        UNWIND $nodes AS n
        MERGE (e:EquipmentType {code: n.code})
        SET e.name = n.name, e.category = n.category, e.updated_at_utc = datetime()
        RETURN count(e) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("EquipmentType taxonomy sync failed: %s", exc)
            return 0

    def _sync_market_nodes(self) -> int:
        """Upsert Market nodes from res.country.state (US states as markets).

        Market nodes represent geographic trading regions. For US-based
        plastics recycling, each US state is a market node.
        """
        State = self.env["res.country.state"]
        us_country = self.env.ref("base.us", raise_if_not_found=False)
        if not us_country:
            return 0
        states = State.search([("country_id", "=", us_country.id)])
        if not states:
            return 0
        country_code = us_country.code
        payloads = [{"code": s.code, "name": s.name, "country": country_code} for s in states]
        query = """
        UNWIND $nodes AS n
        MERGE (m:Market {code: n.code})
        SET m.name = n.name, m.country = n.country, m.updated_at_utc = datetime()
        RETURN count(m) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"nodes": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("Market taxonomy sync failed: %s", exc)
            return 0

    # ═════════════════════════════════════════════════════════
    # Phase 3: Facility Capability Edges
    # ═════════════════════════════════════════════════════════
    def sync_facility_edges(self, trigger="manual"):
        """Materialize facility capability edges.

        Edges: ACCEPTS_POLYMER, ACCEPTS_FORM, OPERATES_PROCESS,
        HAS_EQUIPMENT, LOCATED_IN_MARKET.
        """
        total = 0
        total += self._sync_accepts_polymer_edges()
        total += self._sync_accepts_form_edges()
        total += self._sync_operates_process_edges()
        total += self._sync_has_equipment_edges()
        total += self._sync_located_in_market_edges()
        self._create_sync_log("facility_edges", "success", {"records_processed": total, "trigger": trigger}, None)

    def _sync_accepts_polymer_edges(self) -> int:
        """Create ACCEPTS_POLYMER edges: Facility -> Polymer.

        Based on facility_profile.accepted_polymer_ids Many2many.
        """
        partners = self.env["res.partner"].search([("facility_profile_ids", "!=", False)])
        payloads = []
        for partner in partners:
            for fp in partner.facility_profile_ids.filtered(lambda p: p.active):
                for poly in fp.accepted_polymer_ids:
                    if poly.code:
                        payloads.append({"facility_id": partner.id, "polymer_code": poly.code})
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (fac:Facility {facility_id: e.facility_id})
        MATCH (p:Polymer {code: e.polymer_code})
        MERGE (fac)-[r:ACCEPTS_POLYMER]->(p)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("ACCEPTS_POLYMER edge sync failed: %s", exc)
            return 0

    def _sync_accepts_form_edges(self) -> int:
        """Create ACCEPTS_FORM edges: Facility -> MaterialForm.

        Based on facility_profile.form_preference_id Many2one.
        """
        partners = self.env["res.partner"].search([("facility_profile_ids", "!=", False)])
        payloads = []
        for partner in partners:
            for fp in partner.facility_profile_ids.filtered(lambda p: p.active):
                if fp.form_preference_id and fp.form_preference_id.code:
                    payloads.append({"facility_id": partner.id, "form_code": fp.form_preference_id.code})
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (fac:Facility {facility_id: e.facility_id})
        MATCH (f:MaterialForm {code: e.form_code})
        MERGE (fac)-[r:ACCEPTS_FORM]->(f)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("ACCEPTS_FORM edge sync failed: %s", exc)
            return 0

    def _sync_operates_process_edges(self) -> int:
        """Create OPERATES_PROCESS edges: Facility -> ProcessType.

        Based on facility_profile.process_type Selection field.
        """
        partners = self.env["res.partner"].search([("facility_profile_ids", "!=", False)])
        payloads = []
        for partner in partners:
            for fp in partner.facility_profile_ids.filtered(lambda p: p.active):
                if fp.process_type:
                    payloads.append({"facility_id": partner.id, "process_code": fp.process_type})
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (fac:Facility {facility_id: e.facility_id})
        MATCH (p:ProcessType {code: e.process_code})
        MERGE (fac)-[r:OPERATES_PROCESS]->(p)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("OPERATES_PROCESS edge sync failed: %s", exc)
            return 0

    def _sync_has_equipment_edges(self) -> int:
        """Create HAS_EQUIPMENT edges: Facility -> EquipmentType.

        Based on facility_profile.equipment_type_ids Many2many.
        """
        partners = self.env["res.partner"].search([("facility_profile_ids", "!=", False)])
        payloads = []
        for partner in partners:
            for fp in partner.facility_profile_ids.filtered(lambda p: p.active):
                for eq in fp.equipment_type_ids:
                    if eq.code:
                        payloads.append({"facility_id": partner.id, "equipment_code": eq.code})
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (fac:Facility {facility_id: e.facility_id})
        MATCH (eq:EquipmentType {code: e.equipment_code})
        MERGE (fac)-[r:HAS_EQUIPMENT]->(eq)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("HAS_EQUIPMENT edge sync failed: %s", exc)
            return 0

    def _sync_located_in_market_edges(self) -> int:
        """Create LOCATED_IN_MARKET edges: Facility -> Market.

        Based on partner.state_id (US state as market region).
        """
        partners = self.env["res.partner"].search([("facility_profile_ids", "!=", False), ("state_id", "!=", False)])
        payloads = []
        for partner in partners:
            if partner.state_id and partner.state_id.code:
                payloads.append({"facility_id": partner.id, "market_code": partner.state_id.code})
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (fac:Facility {facility_id: e.facility_id})
        MATCH (m:Market {code: e.market_code})
        MERGE (fac)-[r:LOCATED_IN_MARKET]->(m)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("LOCATED_IN_MARKET edge sync failed: %s", exc)
            return 0

    # ═════════════════════════════════════════════════════════
    # Phase 4: Material Classification Edges
    # ═════════════════════════════════════════════════════════
    def sync_material_edges(self, trigger="manual"):
        """Materialize material classification edges.

        Edges: IS_POLYMER, HAS_FORM, HAS_COLOR, HAS_SOURCE_TYPE.
        """
        total = 0
        total += self._sync_is_polymer_edges()
        total += self._sync_has_form_edges()
        total += self._sync_has_color_edges()
        total += self._sync_has_source_type_edges()
        self._create_sync_log("material_edges", "success", {"records_processed": total, "trigger": trigger}, None)

    def _sync_is_polymer_edges(self) -> int:
        """Create IS_POLYMER edges: MaterialProfile -> Polymer."""
        materials = self.env["plasticos.material.profile"].search([("active", "=", True), ("polymer_id", "!=", False)])
        payloads = [
            {"material_id": mp.id, "polymer_code": mp.polymer_id.code} for mp in materials if mp.polymer_id.code
        ]
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (mat:MaterialProfile {material_id: e.material_id})
        MATCH (p:Polymer {code: e.polymer_code})
        MERGE (mat)-[r:IS_POLYMER]->(p)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("IS_POLYMER edge sync failed: %s", exc)
            return 0

    def _sync_has_form_edges(self) -> int:
        """Create HAS_FORM edges: MaterialProfile -> MaterialForm."""
        materials = self.env["plasticos.material.profile"].search([("active", "=", True), ("form_id", "!=", False)])
        payloads = [{"material_id": mp.id, "form_code": mp.form_id.code} for mp in materials if mp.form_id.code]
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (mat:MaterialProfile {material_id: e.material_id})
        MATCH (f:MaterialForm {code: e.form_code})
        MERGE (mat)-[r:HAS_FORM]->(f)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("HAS_FORM edge sync failed: %s", exc)
            return 0

    def _sync_has_color_edges(self) -> int:
        """Create HAS_COLOR edges: MaterialProfile -> MaterialColor."""
        materials = self.env["plasticos.material.profile"].search([("active", "=", True), ("color_id", "!=", False)])
        payloads = [{"material_id": mp.id, "color_code": mp.color_id.code} for mp in materials if mp.color_id.code]
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (mat:MaterialProfile {material_id: e.material_id})
        MATCH (c:MaterialColor {code: e.color_code})
        MERGE (mat)-[r:HAS_COLOR]->(c)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("HAS_COLOR edge sync failed: %s", exc)
            return 0

    def _sync_has_source_type_edges(self) -> int:
        """Create HAS_SOURCE_TYPE edges: MaterialProfile -> SourceType."""
        materials = self.env["plasticos.material.profile"].search(
            [("active", "=", True), ("source_type_id", "!=", False)]
        )
        payloads = [
            {"material_id": mp.id, "source_code": mp.source_type_id.code} for mp in materials if mp.source_type_id.code
        ]
        if not payloads:
            return 0
        query = """
        UNWIND $edges AS e
        MATCH (mat:MaterialProfile {material_id: e.material_id})
        MATCH (s:SourceType {code: e.source_code})
        MERGE (mat)-[r:HAS_SOURCE_TYPE]->(s)
        SET r.updated_at_utc = datetime()
        RETURN count(r) AS cnt
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            return rows[0].get("cnt", 0) if rows else len(payloads)
        except Exception as exc:
            _logger.warning("HAS_SOURCE_TYPE edge sync failed: %s", exc)
            return 0

    # ═════════════════════════════════════════════════════════
    # Phase 6: Exclusion Negative-Signal Edges
    # ═════════════════════════════════════════════════════════
    def sync_exclusion_edges(self, trigger="manual"):
        """Sync EXCLUDED_FROM edges from plasticos.match.exclusion.

        Creates (:Facility)-[:EXCLUDED_FROM]->(:Facility) edges.
        Removes expired/inactive exclusions from the graph.
        """
        if "plasticos.match.exclusion" not in self.env:
            self._create_sync_log("exclusion", "success", {"records_processed": 0}, None)
            return

        Exclusion = self.env["plasticos.match.exclusion"]
        today = fields.Date.today()

        # Active exclusions: permanent OR temporary with future expiry
        active_exclusions = Exclusion.search(
            [
                ("active", "=", True),
                "|",
                ("exclusion_type", "=", "permanent"),
                "&",
                ("exclusion_type", "=", "temporary"),
                ("expiry_date", ">=", today),
            ],
            order="id ASC",
        )

        # Build active edge payloads
        payloads = [
            {
                "supplier_id": exc.supplier_partner_id.id,
                "buyer_id": exc.buyer_partner_id.id,
                "exclusion_type": exc.exclusion_type,
                "reason": exc.reason or "",
                "expiry_date": exc.expiry_date.isoformat() if exc.expiry_date else None,
            }
            for exc in active_exclusions
        ]

        total = 0
        if payloads:
            upsert_query = """
            UNWIND $edges AS e
            MATCH (supplier:Facility {facility_id: e.supplier_id})
            MATCH (buyer:Facility {facility_id: e.buyer_id})
            MERGE (supplier)-[r:EXCLUDED_FROM]->(buyer)
            SET r.exclusion_type = e.exclusion_type,
                r.reason = e.reason,
                r.expiry_date = e.expiry_date,
                r.updated_at_utc = datetime()
            RETURN count(r) AS cnt
            """
            try:
                rows = self._execute_cypher(upsert_query, {"edges": payloads})
                total = rows[0].get("cnt", 0) if rows else len(payloads)
            except Exception as exc:
                _logger.warning("EXCLUDED_FROM edge upsert failed: %s", exc)

        # Cleanup: remove EXCLUDED_FROM edges for expired/inactive exclusions
        cleanup_query = """
        MATCH (s:Facility)-[r:EXCLUDED_FROM]->(b:Facility)
        WHERE r.expiry_date IS NOT NULL AND date(r.expiry_date) < date()
        DELETE r
        RETURN count(r) AS removed
        """
        try:
            rows = self._execute_cypher(cleanup_query)
            removed = rows[0].get("removed", 0) if rows else 0
            if removed:
                _logger.info("Removed %d expired EXCLUDED_FROM edges.", removed)
        except Exception as exc:
            _logger.warning("EXCLUDED_FROM cleanup failed: %s", exc)

        self._create_sync_log("exclusion", "success", {"records_processed": total, "trigger": trigger}, None)

    def sync_transaction_edges(self, trigger="manual"):
        """Sync SOLD_TO edges from plasticos.transaction records.

        Ontology v2.0: SOLD_TO links MaterialProfile -> Facility (buyer).
        Creates edges between supplier materials and buyer facilities with:
        - tx_count: Number of transactions between the pair
        - total_volume_lbs: Cumulative volume across transactions
        - last_tx_date: Date of most recent transaction
        - avg_price_per_lb: Average price per pound (if available)
        """

        # Check if plasticos.transaction model exists
        if "plasticos.transaction" not in self.env:
            self._create_sync_log("transaction", "success", {"records_processed": 0}, None)
            return

        # Aggregate transactions by supplier-buyer pair
        Transaction = self.env["plasticos.transaction"]
        transactions = Transaction.search(
            [
                ("supplier_id", "!=", False),
                ("buyer_id", "!=", False),
                ("state", "not in", ["cancelled", "draft"]),
            ]
        )

        if not transactions:
            self._create_sync_log("transaction", "success", {"records_processed": 0}, None)
            return

        # Build aggregated edge payloads: {(supplier_id, buyer_id): {count, last_date, volume}}
        edge_data: dict[tuple[int, int], dict] = {}
        for tx in transactions:
            key = (tx.supplier_id.id, tx.buyer_id.id)
            tx_date = tx.create_date.date() if tx.create_date else None
            qty = getattr(tx, "quantity_lbs", 0) or 0
            price = getattr(tx, "price_per_lb", 0) or 0
            if key not in edge_data:
                edge_data[key] = {
                    "tx_count": 0,
                    "last_tx_date": None,
                    "total_volume_lbs": 0,
                    "total_price_value": 0.0,
                }
            edge_data[key]["tx_count"] += 1
            edge_data[key]["total_volume_lbs"] += qty
            edge_data[key]["total_price_value"] += price * qty if price and qty else 0
            if tx_date and (edge_data[key]["last_tx_date"] is None or tx_date > edge_data[key]["last_tx_date"]):
                edge_data[key]["last_tx_date"] = tx_date

        # Convert to list of payloads
        payloads = [
            {
                "supplier_id": supplier_id,
                "buyer_id": buyer_id,
                "tx_count": data["tx_count"],
                "total_volume_lbs": data["total_volume_lbs"],
                "avg_price_per_lb": (
                    round(data["total_price_value"] / data["total_volume_lbs"], 4) if data["total_volume_lbs"] else None
                ),
                "last_tx_date": data["last_tx_date"].isoformat() if data["last_tx_date"] else None,
            }
            for (supplier_id, buyer_id), data in edge_data.items()
        ]

        if not payloads:
            self._create_sync_log("transaction", "success", {"records_processed": 0}, None)
            return

        # Schema: SOLD_TO links MaterialProfile -> Facility (ontology v2.0)
        # Fallback: when no MaterialProfile exists, link Facility -> Facility
        query = """
        UNWIND $edges AS e
        MATCH (supplier:Facility {facility_id: e.supplier_id})
        MATCH (buyer:Facility {facility_id: e.buyer_id})
        OPTIONAL MATCH (supplier)-[:HAS_MATERIAL]->(mat:MaterialProfile)
        WITH supplier, buyer, e, collect(mat)[0] AS first_mat
        FOREACH (_ IN CASE WHEN first_mat IS NOT NULL THEN [1] ELSE [] END |
            MERGE (first_mat)-[tx:SOLD_TO]->(buyer)
            ON CREATE SET
                tx.tx_count = e.tx_count,
                tx.total_volume_lbs = e.total_volume_lbs,
                tx.avg_price_per_lb = e.avg_price_per_lb,
                tx.last_tx_date = e.last_tx_date,
                tx.created_at_utc = datetime()
            ON MATCH SET
                tx.tx_count = e.tx_count,
                tx.total_volume_lbs = e.total_volume_lbs,
                tx.avg_price_per_lb = e.avg_price_per_lb,
                tx.last_tx_date = e.last_tx_date,
                tx.updated_at_utc = datetime()
        )
        RETURN count(supplier) AS n
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            n = (rows[0].get("n", 0) if rows else 0) or len(payloads)
            self._create_sync_log("transaction", "success", {"records_processed": n, "trigger": trigger}, None)
        except Exception as exc:
            self._create_sync_log("transaction", "failed", None, str(exc))

    def _create_sync_log(self, sync_type, status, stats=None, error_message=None):
        Log = self.env["plasticos.graph.sync.log"].sudo()
        name = f"Graph sync {sync_type} {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        record_count = (stats or {}).get("records_processed", 0)
        Log.create(
            {
                "name": name,
                "sync_type": sync_type,
                "record_count": record_count,
                "status": status,
                "error_message": error_message,
                "started_at": fields.Datetime.now(),
                "finished_at": fields.Datetime.now(),
            }
        )
