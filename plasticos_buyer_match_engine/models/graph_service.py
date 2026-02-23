"""Neo4j graph orchestration for buyer matching.

Implements plasticos.graph.service (AbstractModel): sync Facility/MaterialProfile
nodes and run graph traversal for match_buyers_for_intake.

Architecture:
    - services/neo4j_pool.py: Connection pooling with circuit breaker
    - services/monitoring.py: Metrics collection (timing, counters)

Public API:
    - execute_cypher_query(): Pooled + metrics, raises UserError on failure
    - _execute_cypher(): Optional/graceful, returns [] on failure (for hooks)
    - sync_facility_nodes(), sync_material_nodes(), sync_all(): Graph sync
    - match_buyers_for_intake(): Graph-based buyer matching
"""

import logging
import os
from datetime import datetime

from odoo import fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _env_neo4j_uri():
    """Neo4j URI from environment (.env): NEO4J_URI or NEO4J_URL."""
    return os.environ.get("NEO4J_URI") or os.environ.get("NEO4J_URL") or ""


def _env_neo4j_user():
    return os.environ.get("NEO4J_USER", "")


def _env_neo4j_password():
    return os.environ.get("NEO4J_PASSWORD", "")


try:
    from neo4j.exceptions import Neo4jError, ServiceUnavailable
except ImportError:
    Neo4jError = Exception
    ServiceUnavailable = Exception


def _neo4j_pool():
    from odoo.addons.plasticos_buyer_match_engine.services import neo4j_pool

    return neo4j_pool.Neo4jConnectionPool


class PlasticosGraphService(models.AbstractModel):
    _name = "plasticos.graph.service"
    _description = "PlastOS Graph Engine (Neo4j buyer matching)"

    def _get_config(self):
        """Return Neo4j connection and match config.

        Uri, user, password: from System Parameters (plasticos_graph.*) with
        fallback to .env (NEO4J_URI or NEO4J_URL, NEO4J_USER, NEO4J_PASSWORD).
        """
        self.ensure_one()
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

    def _get_pool(self):
        """Return shared Neo4jConnectionPool; raises UserError if Neo4j not configured."""
        self.ensure_one()
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
        from odoo.addons.plasticos_buyer_match_engine.services.monitoring import get_metrics

        self.ensure_one()
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
                "Neo4j service is unavailable. Please try again later or " "contact your administrator."
            ) from exc

        except Neo4jError as exc:
            metrics.increment(f"{op_name}.neo4j_error")
            _logger.error(
                "Neo4j error: %s | metadata=%s",
                exc,
                metadata,
                exc_info=True,
            )
            raise UserError("Neo4j query failed:\n%s" % (getattr(exc, "message", str(exc)))) from exc

        except Exception as exc:
            metrics.increment(f"{op_name}.unexpected_error")
            _logger.exception(
                "Unexpected error while executing Neo4j query | metadata=%s",
                metadata,
            )
            raise UserError("Unexpected error while communicating with Neo4j. " "Check Odoo logs for details.") from exc

    def _get_driver(self):
        """Return pool or None when Neo4j is optional (hooks/sync); no UserError."""
        self.ensure_one()
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
        self.ensure_one()
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
        self.ensure_one()
        driver = self._get_driver()
        if not driver or not driver.driver:
            return
        constraints = [
            "CREATE CONSTRAINT facility_id IF NOT EXISTS FOR (f:Facility) REQUIRE f.facility_id IS UNIQUE",
            "CREATE CONSTRAINT material_id IF NOT EXISTS FOR (m:MaterialProfile) REQUIRE m.material_id IS UNIQUE",
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
        self.ensure_one()
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
            payloads.append(
                {
                    "facility_id": partner.id,
                    "partner_id": partner.id,
                    "name": partner.name or "",
                    "is_buyer": bool(any(getattr(fp, "is_buyer", True) for fp in profiles)),
                    "is_supplier": bool(any(getattr(fp, "is_supplier", True) for fp in profiles)),
                    "lat": partner.partner_latitude or None,
                    "lon": partner.partner_longitude or None,
                    "city": partner.city or None,
                    "state": partner.state_id.code if partner.state_id else None,
                    "country": partner.country_id.code if partner.country_id else None,
                    "can_remove_metal": any(getattr(fp, "can_remove_metal", False) for fp in profiles),
                    "can_filter_fr": any(getattr(fp, "can_filter_fr", False) for fp in profiles),
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
        self.ensure_one()
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
                }
            )
        return payloads

    def sync_facility_nodes(self, trigger="manual"):
        """Upsert Facility nodes with geo location as Neo4j point."""
        self.ensure_one()
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
            fac.is_buyer          = coalesce(f.is_buyer, false),
            fac.is_supplier       = coalesce(f.is_supplier, false),
            fac.can_remove_metal  = coalesce(f.can_remove_metal, false),
            fac.can_filter_fr     = coalesce(f.can_filter_fr, false),
            fac.min_lot_size_lbs  = f.min_lot_size_lbs,
            fac.max_lot_size_lbs  = f.max_lot_size_lbs,
            fac.city              = f.city,
            fac.state             = f.state,
            fac.country           = f.country,
            fac.created_at_utc    = datetime(),
            fac.updated_at_utc    = datetime()
        ON MATCH SET
            fac.partner_id        = f.partner_id,
            fac.name              = f.name,
            fac.is_buyer          = coalesce(f.is_buyer, fac.is_buyer),
            fac.is_supplier       = coalesce(f.is_supplier, fac.is_supplier),
            fac.can_remove_metal  = coalesce(f.can_remove_metal, fac.can_remove_metal),
            fac.can_filter_fr     = coalesce(f.can_filter_fr, fac.can_filter_fr),
            fac.min_lot_size_lbs  = f.min_lot_size_lbs,
            fac.max_lot_size_lbs  = f.max_lot_size_lbs,
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
        self.ensure_one()
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
            mat.created_at_utc = datetime(), mat.updated_at_utc = datetime()
        ON MATCH SET
            mat.facility_id = m.facility_id, mat.polymer = m.polymer, mat.form = m.form,
            mat.color = m.color, mat.updated_at_utc = datetime()
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
        self.ensure_one()
        self.initialize_schema()
        self.sync_facility_nodes(trigger=trigger)
        self.sync_material_nodes(trigger=trigger)
        self._create_sync_log("full", "success", {"trigger": trigger}, None)

    def sync_transaction_edges(self, trigger="manual"):
        self.ensure_one()
        # No-op unless plasticos_transaction is wired to graph
        self._create_sync_log("transaction", "success", {"records_processed": 0}, None)

    def _create_sync_log(self, sync_type, status, stats=None, error_message=None):
        self.ensure_one()
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

    def _intake_to_match_params(self, intake):
        self.ensure_one()
        mat = intake.material_profile_id
        if not mat:
            return None
        polymer = mat.polymer_id.code if mat.polymer_id else (getattr(mat, "polymer", None) or "")
        form = mat.form_id.code if mat.form_id else (getattr(mat, "form", None) or "")
        lat = (
            getattr(intake, "lat", None)
            or (intake.partner_id and getattr(intake.partner_id, "partner_latitude", None))
            or None
        )
        lon = (
            getattr(intake, "lon", None)
            or (intake.partner_id and getattr(intake.partner_id, "partner_longitude", None))
            or None
        )
        cfg = self._get_config()
        return {
            "polymer": polymer,
            "form": form,
            "lat": lat,
            "lon": lon,
            "max_distance_km": cfg.get("max_distance_km", 500 * 1.60934),
            "limit": cfg.get("match_max_results", 25),
        }

    def match_buyers_for_intake(self, intake):
        """Run graph-based buyer match with geo distance filtering.

        Uses Neo4j's point() and distance() functions for geo filtering when
        intake has lat/lon coordinates. Falls back to material-only matching
        if no coordinates available.
        """
        self.ensure_one()
        params = self._intake_to_match_params(intake)
        if not params or not params.get("polymer") or not params.get("form"):
            return []

        # Use geo-aware query if we have coordinates
        has_geo = params.get("lat") is not None and params.get("lon") is not None

        if has_geo:
            query = """
            // Create origin point from intake coordinates
            WITH point({latitude: $lat, longitude: $lon}) AS origin

            MATCH (fac:Facility {is_buyer: true})-[:HAS_MATERIAL]->(m:MaterialProfile)
            WHERE m.polymer = $polymer AND m.form = $form
              AND fac.location IS NOT NULL
              AND distance(origin, fac.location) <= $max_distance_km * 1000

            RETURN fac.facility_id AS facility_partner_id,
                   distance(origin, fac.location) / 1000.0 AS distance_km
            ORDER BY distance_km ASC
            LIMIT $limit
            """
        else:
            # Fallback: material-only matching without geo filter
            query = """
            MATCH (fac:Facility {is_buyer: true})-[:HAS_MATERIAL]->(m:MaterialProfile)
            WHERE m.polymer = $polymer AND m.form = $form
            RETURN fac.facility_id AS facility_partner_id, null AS distance_km
            LIMIT $limit
            """

        rows = self._execute_cypher(query, params)
        if not rows:
            return []

        Match = self.env["plasticos.match.result"].sudo()
        Match.search([("intake_id", "=", intake.id), ("l9_run_id", "=", "graph")]).unlink()
        FacilityProfile = self.env["plasticos.facility.profile"].sudo()

        for rank, row in enumerate(rows, start=1):
            partner_id = row.get("facility_partner_id")
            if not partner_id:
                continue
            facility_profile = FacilityProfile.search([("partner_id", "=", partner_id)], limit=1)
            distance_km = row.get("distance_km")

            # Score: closer = higher score (100 - distance penalty)
            if distance_km is not None:
                distance_penalty = min(distance_km / 10.0, 50.0)  # Max 50 point penalty
                score = max(0.0, 100.0 - distance_penalty - (rank - 1) * 2)
            else:
                score = max(0.0, 100.0 - rank * 2)

            breakdown = {"rank": rank, "source": "graph"}
            if distance_km is not None:
                breakdown["distance_km"] = round(distance_km, 1)

            Match.create(
                {
                    "intake_id": intake.id,
                    "buyer_partner_id": partner_id,
                    "facility_profile_id": facility_profile.id if facility_profile else False,
                    "score": score,
                    "confidence": 100.0,
                    "score_breakdown": breakdown,
                    "match_reasoning": f"Graph match #{rank} (polymer/form"
                    + (f", {distance_km:.0f}km away)" if distance_km else ")"),
                    "state": "pending",
                    "l9_run_id": "graph",
                    "l9_timestamp": fields.Datetime.now(),
                }
            )
        return rows
