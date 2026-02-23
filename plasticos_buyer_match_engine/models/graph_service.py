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

from odoo import fields, models  # pyright: ignore[reportMissingImports]
from odoo.exceptions import UserError  # pyright: ignore[reportMissingImports]

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
        from ..services.monitoring import get_metrics  # Relative import for pyright

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
            # Equipment flags: True if ANY profile has the capability
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
            // Location
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
            // Location
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
        self.sync_transaction_edges(trigger=trigger)
        self._create_sync_log("full", "success", {"trigger": trigger}, None)

    def sync_transaction_edges(self, trigger="manual"):
        """Sync TRANSACTED_WITH edges from plasticos.transaction records.

        Creates edges between supplier and buyer facilities with:
        - tx_count: Number of transactions between the pair
        - last_tx_date: Date of most recent transaction
        """
        self.ensure_one()

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
                ("state", "not in", ["cancel", "draft"]),
            ]
        )

        if not transactions:
            self._create_sync_log("transaction", "success", {"records_processed": 0}, None)
            return

        # Build aggregated edge payloads: {(supplier_id, buyer_id): {count, last_date}}
        edge_data = {}
        for tx in transactions:
            key = (tx.supplier_id.id, tx.buyer_id.id)
            tx_date = tx.create_date.date() if tx.create_date else None
            if key not in edge_data:
                edge_data[key] = {"tx_count": 0, "last_tx_date": None}
            edge_data[key]["tx_count"] += 1
            if tx_date and (edge_data[key]["last_tx_date"] is None or tx_date > edge_data[key]["last_tx_date"]):
                edge_data[key]["last_tx_date"] = tx_date

        # Convert to list of payloads
        payloads = [
            {
                "supplier_id": supplier_id,
                "buyer_id": buyer_id,
                "tx_count": data["tx_count"],
                "last_tx_date": data["last_tx_date"].isoformat() if data["last_tx_date"] else None,
            }
            for (supplier_id, buyer_id), data in edge_data.items()
        ]

        if not payloads:
            self._create_sync_log("transaction", "success", {"records_processed": 0}, None)
            return

        query = """
        UNWIND $edges AS e
        MATCH (supplier:Facility {facility_id: e.supplier_id})
        MATCH (buyer:Facility {facility_id: e.buyer_id})
        MERGE (supplier)-[tx:TRANSACTED_WITH]->(buyer)
        ON CREATE SET
            tx.tx_count = e.tx_count,
            tx.last_tx_date = e.last_tx_date,
            tx.created_at_utc = datetime()
        ON MATCH SET
            tx.tx_count = e.tx_count,
            tx.last_tx_date = e.last_tx_date,
            tx.updated_at_utc = datetime()
        RETURN count(tx) AS n
        """
        try:
            rows = self._execute_cypher(query, {"edges": payloads})
            n = (rows[0].get("n", 0) if rows else 0) or len(payloads)
            self._create_sync_log("transaction", "success", {"records_processed": n, "trigger": trigger}, None)
        except Exception as exc:
            self._create_sync_log("transaction", "failed", None, str(exc))

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
        """Map intake record to Cypher params for advanced buyer match.

        Extracts all parameters needed for the 10 hard gates + 7 soft signals
        from the 45-step reasoning framework:

        Hard Gates (binary exclusions):
        1. polymer - exact polymer match
        2. accepted_polymers - facility accepts this polymer
        3. density_min/max - material density within buyer's range
        4. melt_index_min/max - MFI within buyer's processing range
        5. contamination_tolerance_pct - buyer can handle contamination level
        6. moisture_tolerance_pct - buyer can handle moisture level
        7. has_metal / can_remove_metal - metal detection/removal capability
        8. has_fr / can_filter_fr - flame retardant filtering capability
        9. lot_size_lbs - within buyer's min/max lot size
        10. geo radius - within max distance

        Soft Signals (scoring factors):
        - form, color, source_type, packaging_type, origin_form
        - process_type match, food_grade certification, transaction history

        Equipment Capability Gates (from 45-step framework):
        - has_wash_line - required if dirt > 1%
        - has_dryer - required if moisture > 500 ppm
        - handles_bales/regrind/pellet/flake - form handling capability
        """
        self.ensure_one()
        mat = intake.material_profile_id
        if not mat:
            return None

        # ── Core identifiers ─────────────────────────────────────────────
        polymer = mat.polymer_id.code if mat.polymer_id else (getattr(mat, "polymer", None) or "")
        form = mat.form_id.code if mat.form_id else (getattr(mat, "form", None) or "")

        # ── Geo coordinates ──────────────────────────────────────────────
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

        # ── Material properties (for hard gates) ─────────────────────────
        density = getattr(mat, "density", None) or getattr(mat, "specific_gravity", None)
        mfi = getattr(mat, "melt_index", None) or getattr(mat, "mfi", None)

        # ── Contamination levels (for hard gates) ────────────────────────
        contamination_pct = (
            getattr(mat, "contamination_pct", None)
            or getattr(mat, "contamination_level", None)
            or getattr(intake, "contamination_pct", None)
            or 0.0
        )
        moisture_pct = (
            getattr(mat, "moisture_pct", None)
            or getattr(mat, "moisture_content", None)
            or getattr(intake, "moisture_pct", None)
            or 0.0
        )
        # Convert ppm to pct if needed (moisture often in ppm)
        if moisture_pct and moisture_pct > 100:
            moisture_pct = moisture_pct / 10000.0  # ppm to %

        # ── Contamination flags (for capability gates) ───────────────────
        # Extract material attribute codes for contamination inference
        attr_codes = set()
        if hasattr(mat, "material_attribute_ids") and mat.material_attribute_ids:
            attr_codes = set(mat.material_attribute_ids.mapped("code"))

        has_metal = bool(
            getattr(mat, "has_metal", False)
            or getattr(mat, "metal_detected", False)
            or getattr(intake, "has_metal", False)
            or "with_metal" in attr_codes
        )
        has_fr = bool(
            getattr(mat, "has_flame_retardant", False)
            or getattr(mat, "has_fr", False)
            or getattr(intake, "has_fr", False)
        )
        # Cross-polymer contamination (inferred from material attributes)
        has_pvc = bool(
            getattr(mat, "has_pvc", False) or getattr(intake, "has_pvc", False) or "pvc_contaminated" in attr_codes
        )
        has_pp_contamination = bool(
            getattr(mat, "has_pp_contamination", False)
            or getattr(intake, "has_pp_contamination", False)
            or "pp_contaminated" in attr_codes
        )

        # ── Lot size ─────────────────────────────────────────────────────
        lot_size_lbs = (
            getattr(intake, "weight_lbs", None)
            or getattr(intake, "quantity_lbs", None)
            or getattr(intake, "lot_size_lbs", None)
            or 0.0
        )

        # ── Soft signal attributes ───────────────────────────────────────
        color = getattr(mat, "color", None) or getattr(mat, "color_code", None)
        source_type = (
            getattr(mat, "source_type", None)
            or getattr(mat, "material_source", None)
            or getattr(intake, "source_type", None)
        )
        packaging_type = getattr(mat, "packaging_type", None) or getattr(intake, "packaging_type", None)
        origin_form = getattr(mat, "origin_form", None) or getattr(mat, "original_form", None)
        origin_process_type = getattr(mat, "origin_process_type", None) or getattr(mat, "process_type", None)

        # ── Certification requirements ───────────────────────────────────
        food_grade = bool(
            getattr(mat, "food_grade", False)
            or getattr(mat, "food_contact", False)
            or getattr(intake, "food_grade_required", False)
        )
        medical_grade = bool(getattr(mat, "medical_grade", False) or getattr(intake, "medical_grade_required", False))

        # ── Equipment requirement flags (from 45-step framework) ─────────
        # Dirt > 5% requires wash line (Igor: 1% was too aggressive)
        dirt_pct = getattr(mat, "dirt_pct", None) or getattr(intake, "dirt_pct", None) or 0.0
        requires_wash_line = dirt_pct > 5.0 or contamination_pct > 5.0

        # Moisture > 500 ppm (0.05%) requires dryer
        requires_dryer = moisture_pct > 0.05 or (moisture_pct == 0 and getattr(intake, "stored_outdoors", False))

        # ── Filler / Additive fields (45-step framework Layer 4) ──────
        filler_type = mat.filler_type_id.code if mat.filler_type_id else None
        filler_pct = getattr(mat, "filler_pct", None) or 0.0

        # ── Odor / Oil Residue (from attributes) ────────────────────────
        has_odor = "has_odor" in attr_codes
        has_oil_residue = "oil_residue" in attr_codes or "oily" in attr_codes

        # ── Supplier facility for transaction history ────────────────────
        supplier_facility_id = intake.partner_id.id if intake.partner_id else None

        # ── Config ───────────────────────────────────────────────────────
        cfg = self._get_config()
        max_distance_km = cfg.get("max_distance_km", 500 * 1.60934)
        radius_meters = max_distance_km * 1000

        # Build intake point for geo queries
        intake_point = None
        if lat is not None and lon is not None:
            intake_point = {"latitude": lat, "longitude": lon}

        return {
            # ── Hard gate parameters ─────────────────────────────────────
            "polymer": polymer,
            "density": density,
            "mfi": mfi,
            "contamination_pct": contamination_pct,
            "moisture_pct": moisture_pct,
            "has_metal": has_metal,
            "has_fr": has_fr,
            "has_pvc": has_pvc,
            "has_pp_contamination": has_pp_contamination,
            "lot_size_lbs": lot_size_lbs,
            # ── Geo parameters ───────────────────────────────────────────
            "intake_point": intake_point,
            "radius_meters": radius_meters,
            "lat": lat,
            "lon": lon,
            "max_distance_km": max_distance_km,
            # ── Soft signal parameters ───────────────────────────────────
            "form": form,
            "color": color,
            "source_type": source_type,
            "packaging_type": packaging_type,
            "origin_form": origin_form,
            "origin_process_type": origin_process_type,
            # ── Certification requirements ───────────────────────────────
            "food_grade": food_grade,
            "medical_grade": medical_grade,
            # ── Equipment requirement flags ──────────────────────────────
            "requires_wash_line": requires_wash_line,
            "requires_dryer": requires_dryer,
            "dirt_pct": dirt_pct,
            # ── Filler / Additive parameters ─────────────────────────────
            "filler_type": filler_type,
            "filler_pct": filler_pct,
            # ── Odor / Oil Residue (attribute-based) ─────────────────────
            "has_odor": has_odor,
            "has_oil_residue": has_oil_residue,
            # ── Transaction history ──────────────────────────────────────
            "supplier_facility_id": supplier_facility_id,
            # ── Scoring weights (configurable) ───────────────────────────
            "w1": float(cfg.get("scoring_w1_hard", 0.50)),
            "w2": float(cfg.get("scoring_w2_soft", 0.15)),
            "w3": float(cfg.get("scoring_w3_geo", 0.25)),
            "w4": float(cfg.get("scoring_w4_tx", 0.10)),
            # ── Limits ───────────────────────────────────────────────────
            "max_results": cfg.get("match_max_results", 25),
        }

    def match_buyers_for_intake(self, intake):
        """Run advanced graph-based buyer match with 10 hard gates + 7 soft signals.

        Implements the 45-step reasoning framework hard gates:

        HARD GATES (binary exclusions - buyer is OUT if any fail):
        1. Polymer match - exact polymer type
        2. Accepted polymers - facility accepts this polymer type
        3. Density range - material density within buyer's min/max
        4. MFI range - melt flow index within buyer's processing capability
        5. Contamination tolerance - buyer can handle contamination level
        6. Moisture tolerance - buyer can handle moisture level
        7. Metal removal - if material has metal, buyer must have removal capability
        8. FR filtering - if material has FR, buyer must have filtering capability
        9. Lot size - within buyer's min/max lot size constraints
        10. Geo radius - within maximum shipping distance

        EQUIPMENT CAPABILITY GATES (from 45-step framework):
        - Wash line required if dirt > 5%
        - Dryer required if moisture > 500 ppm
        - Form handling (bales, regrind, pellet, flake)

        CERTIFICATION GATES:
        - Food grade certification if food contact required
        - Medical grade capability if medical grade required

        SOFT SIGNALS (scoring factors, don't exclude):
        - Form match, color match, source type, packaging type
        - Origin form, process type match, certification bonus
        - Transaction history bonus (repeat business)

        Returns list of matched buyers ranked by composite score.
        """
        self.ensure_one()
        params = self._intake_to_match_params(intake)
        if not params or not params.get("polymer"):
            return []

        # ═══════════════════════════════════════════════════════════════════
        # ADVANCED BUYER MATCH QUERY — 10 Hard Gates + 7 Soft Signals
        # Based on 45-Step Comprehensive Reasoning Framework
        # ═══════════════════════════════════════════════════════════════════
        query = """
        // ══════════════════════════════════════════════════════════════════
        // HARD GATES — Binary exclusions (buyer is OUT if any fail)
        // ══════════════════════════════════════════════════════════════════

        MATCH (f:Facility)-[:HAS_MATERIAL]->(m:MaterialProfile)
        WHERE f.is_buyer = true
          AND (f.active IS NULL OR f.active = true)

        // ── Hard gate 1: Polymer match on MaterialProfile ─────────────────
        // NOTE: This is the ONLY polymer gate needed. The MaterialProfile
        // already represents what the facility accepts, so checking
        // f.accepted_polymers separately would be redundant.
          AND m.polymer = $polymer

        // ── Hard gate 2: Density range ────────────────────────────────────
          AND (f.density_min IS NULL OR $density IS NULL OR f.density_min <= $density)
          AND (f.density_max IS NULL OR $density IS NULL OR f.density_max >= $density)

        // ── Hard gate 4: MFI (Melt Flow Index) range ──────────────────────
          AND (f.melt_index_min IS NULL OR $mfi IS NULL OR f.melt_index_min <= $mfi)
          AND (f.melt_index_max IS NULL OR $mfi IS NULL OR f.melt_index_max >= $mfi)

        // ── Hard gate 5: Contamination tolerance ──────────────────────────
          AND (f.contamination_tolerance_pct IS NULL
               OR f.contamination_tolerance_pct >= $contamination_pct)

        // ── Hard gate 6: Moisture tolerance ───────────────────────────────
          AND (f.moisture_tolerance_pct IS NULL
               OR f.moisture_tolerance_pct >= $moisture_pct)

        // ── Hard gate 7: Metal removal capability ─────────────────────────
          AND (NOT $has_metal OR f.can_remove_metal = true)

        // ── Hard gate 8: FR (Flame Retardant) filtering capability ────────
          AND (NOT $has_fr OR f.can_filter_fr = true)

        // ── Hard gate 9: Lot size range ───────────────────────────────────
          AND (f.min_lot_size_lbs IS NULL OR $lot_size_lbs = 0
               OR f.min_lot_size_lbs <= $lot_size_lbs)
          AND (f.max_lot_size_lbs IS NULL OR $lot_size_lbs = 0
               OR f.max_lot_size_lbs >= $lot_size_lbs)

        // ══════════════════════════════════════════════════════════════════
        // EQUIPMENT CAPABILITY GATES (from 45-step framework)
        // ══════════════════════════════════════════════════════════════════

        // ── Wash line required if dirt > 5% ───────────────────────────────
          AND (NOT $requires_wash_line OR f.has_wash_line = true)

        // ── Dryer required if moisture > 500 ppm ──────────────────────────
          AND (NOT $requires_dryer OR f.can_reduce_moisture = true)

        // ══════════════════════════════════════════════════════════════════
        // MFI-PROCESS COMPATIBILITY GATE
        // An injection molder CANNOT run blow mold grade (MFI too low)
        // A blow molder CANNOT run high-flow injection grade (parison sag)
        // ══════════════════════════════════════════════════════════════════
          AND CASE f.process_type
            // Injection molding needs MI >= 1.0 for adequate flow length
            WHEN 'injection' THEN ($mfi IS NULL OR $mfi >= 1.0)
            // Blow molding needs MI <= 2.0 for parison integrity
            // HMW-HDPE (MI 0.03-0.5) requires accumulator head
            WHEN 'blow_mold' THEN ($mfi IS NULL OR $mfi <= 2.0)
            // Film blown/cast needs MI 0.5-2.5 for bubble stability
            WHEN 'film_blown' THEN ($mfi IS NULL OR ($mfi >= 0.5 AND $mfi <= 2.5))
            WHEN 'film_cast' THEN ($mfi IS NULL OR ($mfi >= 0.5 AND $mfi <= 2.5))
            // Thermoforming needs MI 1.0-8.0 for sheet flow
            WHEN 'thermoform' THEN ($mfi IS NULL OR ($mfi >= 1.0 AND $mfi <= 8.0))
            // Extrusion (pipe/profile) handles wide range
            WHEN 'extrusion' THEN true
            // Compounding handles everything - they're blending/modifying
            WHEN 'compounding' THEN true
            // Rotomolding needs very low MI (powder sintering)
            WHEN 'rotomold' THEN ($mfi IS NULL OR $mfi <= 5.0)
            ELSE true
          END

        // ══════════════════════════════════════════════════════════════════
        // FORM-EQUIPMENT COMPATIBILITY GATE
        // A buyer without size reduction equipment cannot process bales/parts
        // EXCEPTION: Brokers pass through (they resell, facility profile may be blank)
        // ══════════════════════════════════════════════════════════════════
          AND CASE
            // Brokers pass through - they resell, not process
            WHEN f.facility_role = 'broker' THEN true
            // Non-brokers: check form-equipment compatibility
            ELSE CASE $form
              // Bales require size reduction equipment (granulator or shredder)
              // NULL means facility profile incomplete - allow through
              WHEN 'bales' THEN (f.has_granulator = true OR f.has_shredder = true
                                 OR f.has_granulator IS NULL)
              // Parts require size reduction - shredder for large, granulator for small
              WHEN 'parts' THEN (f.has_granulator = true OR f.has_shredder = true
                                 OR f.has_granulator IS NULL)
              // Regrind can go direct to extruder OR be further processed
              WHEN 'regrind' THEN (f.has_extruder = true
                                   OR f.has_granulator = true
                                   OR f.handles_regrind = true
                                   OR f.has_extruder IS NULL)
              // Flake can go to extruder or be handled directly (wash line NOT required)
              WHEN 'flake' THEN (f.has_extruder = true
                                 OR f.handles_flake = true
                                 OR f.has_extruder IS NULL)
              // Pellets - most equipment can handle, minimal restriction
              WHEN 'pellet' THEN true
              // Purge/lump needs granulator or shredder
              WHEN 'purge' THEN (f.has_granulator = true OR f.has_shredder = true
                                 OR f.has_granulator IS NULL)
              WHEN 'lump' THEN (f.has_granulator = true OR f.has_shredder = true
                                OR f.has_granulator IS NULL)
              // Rollstock - no specific equipment requirement (removed)
              WHEN 'rollstock' THEN true
              ELSE true
            END
          END

        // ══════════════════════════════════════════════════════════════════
        // PVC CONTAMINATION GATE (HDPE/PP processing only)
        // PVC decomposes at HDPE/PP processing temps, releasing HCl
        // Per 45-step framework Step 10:
        //   - EXCLUDE food/medical buyers (ZERO tolerance)
        //   - REQUIRE PVC sorting capability (sorting line with NIR or float-sink)
        // ══════════════════════════════════════════════════════════════════
          AND CASE
            // Only applies when intake is HDPE or PP AND has PVC contamination
            WHEN $polymer IN ['hdpe', 'pp', 'HDPE', 'PP'] AND $has_pvc = true
            THEN (
              // Exclude food/medical buyers entirely (zero tolerance)
              f.food_grade_certified = false
              AND f.medical_grade_capable = false
              // AND require PVC sorting capability
              AND f.has_sorting_line = true
            )
            ELSE true
          END

        // ══════════════════════════════════════════════════════════════════
        // PP CONTAMINATION GATE — REMOVED
        // Igor: "companies can blend HDPE and PP to make a product without
        // compounding!" — This is NOT a hard gate. HDPE/PP blends are common.
        // ══════════════════════════════════════════════════════════════════

        // ══════════════════════════════════════════════════════════════════
        // FILLER COMPATIBILITY GATE (45-step framework Layer 4)
        // Glass-filled material requires buyer who can process glass-filled
        // Filler > 30% typically requires specialized equipment
        // ══════════════════════════════════════════════════════════════════
          AND CASE
            // If material has filler, buyer must accept filled materials
            WHEN $filler_type IS NOT NULL AND $filler_pct > 0
            THEN (
              // Buyer must either: accept this filler type OR be a compounder
              f.accepts_filled_materials = true
              OR f.process_type = 'compounding'
              OR f.accepts_filled_materials IS NULL  // NULL = unknown, allow through
            )
            ELSE true
          END

        // ══════════════════════════════════════════════════════════════════
        // ODOR / OIL RESIDUE GATE (45-step framework Step 30)
        // Has odor or oil residue excludes consumer product applications
        // ══════════════════════════════════════════════════════════════════
          AND CASE
            // Material with odor or oil residue cannot go to consumer product manufacturers
            WHEN $has_odor = true OR $has_oil_residue = true
            THEN (
              // Exclude food, medical, and consumer packaging buyers
              f.food_grade_certified = false
              AND f.medical_grade_capable = false
              AND (f.application_class IS NULL OR f.application_class NOT IN ['food', 'medical', 'packaging'])
            )
            ELSE true
          END

        // ══════════════════════════════════════════════════════════════════
        // CERTIFICATION GATES
        // ══════════════════════════════════════════════════════════════════

        // ── Food grade certification required ─────────────────────────────
          AND (NOT $food_grade OR f.food_grade_certified = true)

        // ── Medical grade capability required ─────────────────────────────
          AND (NOT $medical_grade OR f.medical_grade_capable = true)

        // ══════════════════════════════════════════════════════════════════
        // GEO FILTER (Hard gate 10)
        // ══════════════════════════════════════════════════════════════════
        WITH f, m
        WHERE CASE
          WHEN $intake_point IS NOT NULL AND f.location IS NOT NULL
          THEN point.distance(f.location, point($intake_point)) <= $radius_meters
          ELSE true
        END

        // ══════════════════════════════════════════════════════════════════
        // SOFT SIGNALS — Scoring factors (don't exclude, just rank)
        // ══════════════════════════════════════════════════════════════════
        WITH f, m,
             // Form match (high weight - 40%)
             CASE WHEN m.form = $form THEN 1 ELSE 0 END AS form_match,

             // Color match (25% of soft score)
             CASE WHEN m.color = $color OR $color IS NULL THEN 1 ELSE 0 END AS color_match,

             // Source type match (30% of hard score)
             CASE WHEN m.source_type = $source_type OR $source_type IS NULL
                  THEN 1 ELSE 0 END AS source_match,

             // Packaging type match (5% of soft score)
             CASE WHEN m.packaging_type = $packaging_type OR $packaging_type IS NULL
                  THEN 1 ELSE 0 END AS pkg_match,

             // Origin form match (10% of soft score)
             CASE WHEN m.origin_form = $origin_form OR $origin_form IS NULL
                  THEN 1 ELSE 0 END AS origin_form_match,

             // Process type match (10% of soft score)
             CASE WHEN f.process_type = $origin_process_type OR $origin_process_type IS NULL
                  THEN 1 ELSE 0 END AS process_match,

             // Application class match (soft signal - boost if buyer has specific application focus)
             // Buyers with application_class set are specialized and get a small boost
             CASE WHEN f.application_class IS NOT NULL THEN 0.5 ELSE 0 END AS app_class_match,

             // Certification match (30% of hard score)
             CASE WHEN f.food_grade_certified = true AND $food_grade = true THEN 1
                  WHEN $food_grade = false THEN 1
                  ELSE 0 END AS cert_match,

             // Distance calculation
             CASE
               WHEN $intake_point IS NOT NULL AND f.location IS NOT NULL
               THEN point.distance(f.location, point($intake_point))
               ELSE 0
             END AS distance_m

        // ══════════════════════════════════════════════════════════════════
        // TRANSACTION HISTORY WITH RECENCY WEIGHTING
        // Recent transactions score higher than old ones
        // ══════════════════════════════════════════════════════════════════
        OPTIONAL MATCH (supplier:Facility {facility_id: $supplier_facility_id})
                       -[tx:TRANSACTED_WITH]->(f)

        // ══════════════════════════════════════════════════════════════════
        // COMPOSITE SCORE CALCULATION
        // ══════════════════════════════════════════════════════════════════
        WITH f, m, distance_m,
             form_match, color_match, source_match, pkg_match,
             origin_form_match, process_match, cert_match,
             coalesce(tx.tx_count, 0) AS tx_count,
             // Recency factor: 1.0 for today, decays to 0.5 at 365 days old
             CASE
               WHEN tx.last_tx_date IS NOT NULL
               THEN 0.5 + 0.5 * (1.0 - toFloat(
                 duration.inDays(date(tx.last_tx_date), date()).days
               ) / 365.0)
               ELSE 0.0
             END AS recency_factor,

             // Hard gate score: form + source + cert weighted
             (form_match * 0.40 + source_match * 0.30 + cert_match * 0.30) AS hard_score,

             // Soft signal score (app_class_match adds 5% boost for specialized buyers)
             (color_match * 0.25 + pkg_match * 0.05
              + origin_form_match * 0.10 + process_match * 0.10
              + app_class_match * 0.05 + 0.45) AS soft_raw

        WITH f, m, distance_m, tx_count, recency_factor, hard_score,
             // Clamp soft_raw into 0..1
             CASE WHEN soft_raw > 1.0 THEN 1.0 ELSE soft_raw END AS soft_score,
             // Geo score: 1.0 at 0 distance, 0.0 at radius
             CASE
               WHEN $radius_meters > 0 AND distance_m > 0
               THEN 1.0 - (distance_m / $radius_meters)
               ELSE 1.0
             END AS geo_score

        WITH f, m, distance_m, tx_count, recency_factor, hard_score, soft_score, geo_score,
             // Final weighted score with recency-weighted transaction bonus
             ($w1 * hard_score
              + $w2 * soft_score
              + $w3 * geo_score
              + $w4 * CASE WHEN tx_count > 0
                           THEN (log(1 + tx_count) / log(1 + 100)) *
                                CASE WHEN recency_factor > 0 THEN recency_factor ELSE 0.5 END
                           ELSE 0 END
             ) AS score

        // ══════════════════════════════════════════════════════════════════
        // RETURN RANKED RESULTS
        // ══════════════════════════════════════════════════════════════════
        ORDER BY score DESC
        LIMIT $max_results

        RETURN f.facility_id       AS facility_partner_id,
               f.name              AS facility_name,
               f.process_type      AS process_type,
               m.material_id       AS material_profile_id,
               m.polymer           AS polymer,
               m.form              AS form,
               m.color             AS color,
               round(score * 100) / 100.0 AS score,
               round(distance_m / 1609.34) AS distance_miles,
               round(distance_m / 1000.0, 1) AS distance_km,
               tx_count,
               hard_score,
               soft_score,
               geo_score
        """

        rows = self._execute_cypher(query, params)
        if not rows:
            return []

        # ═══════════════════════════════════════════════════════════════════
        # CREATE MATCH RESULTS IN ODOO
        # ═══════════════════════════════════════════════════════════════════
        Match = self.env["plasticos.match.result"].sudo()
        Match.search([("intake_id", "=", intake.id), ("l9_run_id", "=", "graph_v2")]).unlink()
        FacilityProfile = self.env["plasticos.facility.profile"].sudo()

        for rank, row in enumerate(rows, start=1):
            partner_id = row.get("facility_partner_id")
            if not partner_id:
                continue

            facility_profile = FacilityProfile.search([("partner_id", "=", partner_id)], limit=1)
            score = row.get("score", 0) * 100  # Convert 0-1 to 0-100
            distance_km = row.get("distance_km")
            distance_miles = row.get("distance_miles")

            # Build detailed score breakdown
            breakdown = {
                "rank": rank,
                "source": "graph_v2",
                "hard_score": round(row.get("hard_score", 0) * 100, 1),
                "soft_score": round(row.get("soft_score", 0) * 100, 1),
                "geo_score": round(row.get("geo_score", 0) * 100, 1),
                "tx_count": row.get("tx_count", 0),
            }
            if distance_km is not None:
                breakdown["distance_km"] = round(distance_km, 1)
            if distance_miles is not None:
                breakdown["distance_miles"] = round(distance_miles, 0)

            # Build reasoning string
            reasoning_parts = [f"Graph match #{rank}"]
            reasoning_parts.append(f"polymer={row.get('polymer')}")
            if row.get("form"):
                reasoning_parts.append(f"form={row.get('form')}")
            if distance_miles:
                reasoning_parts.append(f"{distance_miles:.0f}mi away")
            if row.get("tx_count", 0) > 0:
                reasoning_parts.append(f"{row.get('tx_count')} prior transactions")

            Match.create(
                {
                    "intake_id": intake.id,
                    "buyer_partner_id": partner_id,
                    "facility_profile_id": facility_profile.id if facility_profile else False,
                    "score": score,
                    "confidence": 100.0,
                    "score_breakdown": breakdown,
                    "match_reasoning": " | ".join(reasoning_parts),
                    "state": "pending",
                    "l9_run_id": "graph_v2",
                    "l9_timestamp": fields.Datetime.now(),
                }
            )

        return rows

    # ═══════════════════════════════════════════════════════════════════════════
    # TWO-STAGE MATCHING ORCHESTRATOR
    # ═══════════════════════════════════════════════════════════════════════════

    def match_buyers_two_stage(self, intake):
        """Two-stage buyer matching: Capability Matcher → Graph Service.

        STAGE 1 (Capability Matcher):
            - Deterministic hard gates: polymer, form, source_type (exact match)
            - Equipment-based form compatibility
            - Quality gates: contamination, moisture
            - Volume gates: min/max lot size
            - Compliance gates: food/medical grade
            - Geo gate: per-buyer radius
            - Result: Facility IDs that CAN physically accept the material

        STAGE 2 (Graph Service):
            - Range-based gates: MFI, density (inequality comparisons)
            - Equipment capability gates: wash line, dryer
            - Soft signals for scoring: color, packaging, transaction history
            - Result: Ranked list with composite scores

        Why this order?
            - Capability Matcher eliminates noise with fast DB queries
            - Graph Service does expensive graph traversal only on survivors
            - MFI/density are RANGES, not exact matches → Graph handles them

        Returns:
            list[dict]: Ranked matches with scores from both stages
        """
        self.ensure_one()

        if not intake.material_profile_id:
            _logger.warning("match_buyers_two_stage: intake %s has no material_profile_id", intake.id)
            return []

        # ═══════════════════════════════════════════════════════════════════════
        # STAGE 1: Capability Matcher (deterministic hard gates)
        # ═══════════════════════════════════════════════════════════════════════
        from ..services.matcher import PlasticosMatcher

        matcher = PlasticosMatcher(self.env)
        try:
            stage1_results = matcher.match(intake)
        except ValueError as e:
            _logger.warning("Stage 1 matcher failed: %s", e)
            return []

        if not stage1_results:
            _logger.info(
                "match_buyers_two_stage: intake=%s — Stage 1 returned 0 candidates "
                "(no buyers match polymer=%s, form=%s, source_type=%s)",
                intake.name,
                intake.material_profile_id.polymer,
                intake.material_profile_id.form,
                intake.material_profile_id.source_type,
            )
            return []

        # Extract facility partner IDs from Stage 1 survivors
        facility_ids = [r.get("facility_id") for r in stage1_results if r.get("eligible") and r.get("facility_id")]

        if not facility_ids:
            _logger.info("match_buyers_two_stage: intake=%s — Stage 1 had no eligible facilities", intake.name)
            return []

        _logger.info(
            "match_buyers_two_stage: intake=%s — Stage 1 passed %d facilities to Stage 2",
            intake.name,
            len(facility_ids),
        )

        # ═══════════════════════════════════════════════════════════════════════
        # STAGE 2: Graph Service (range gates + scoring)
        # ═══════════════════════════════════════════════════════════════════════
        # Build params with facility filter
        params = self._intake_to_match_params(intake)
        if not params or not params.get("polymer"):
            return []

        # Add facility filter to params
        params["facility_ids"] = facility_ids

        # Modified query with facility filter
        query = self._build_stage2_query()

        rows = self._execute_cypher(query, params)
        if not rows:
            _logger.info(
                "match_buyers_two_stage: intake=%s — Stage 2 graph returned 0 matches "
                "(range gates may have filtered all %d Stage 1 survivors)",
                intake.name,
                len(facility_ids),
            )
            return []

        # ═══════════════════════════════════════════════════════════════════════
        # MERGE RESULTS: Combine Stage 1 distance with Stage 2 scores
        # ═══════════════════════════════════════════════════════════════════════
        stage1_by_facility = {r.get("facility_id"): r for r in stage1_results if r.get("facility_id")}

        merged_results = []
        for row in rows:
            partner_id = row.get("facility_partner_id")
            stage1_data = stage1_by_facility.get(partner_id, {})

            cap = stage1_data.get("capability")
            merged = {
                **row,
                "stage1_distance_miles": stage1_data.get("distance_miles"),
                "stage1_capability_form": cap.form if cap else None,
                "two_stage": True,
            }
            merged_results.append(merged)

        # ═══════════════════════════════════════════════════════════════════════
        # PERSIST TO MATCH RESULTS
        # ═══════════════════════════════════════════════════════════════════════
        self._persist_two_stage_results(intake, merged_results)

        _logger.info(
            "match_buyers_two_stage: intake=%s — Final: %d matches (Stage1: %d → Stage2: %d)",
            intake.name,
            len(merged_results),
            len(facility_ids),
            len(rows),
        )

        return merged_results

    def _build_stage2_query(self):
        """Build Stage 2 Cypher query with facility filter.

        Same as match_buyers_for_intake query but adds:
            - WHERE f.facility_id IN $facility_ids (filter to Stage 1 survivors)
        """
        return """
        // ══════════════════════════════════════════════════════════════════
        // STAGE 2: Range Gates + Scoring (filtered to Stage 1 survivors)
        // ══════════════════════════════════════════════════════════════════

        MATCH (f:Facility)-[:HAS_MATERIAL]->(m:MaterialProfile)
        WHERE f.is_buyer = true
          AND (f.active IS NULL OR f.active = true)

        // ── Stage 1 survivor filter ─────────────────────────────────────────
          AND f.facility_id IN $facility_ids

        // ── Polymer match (should already be filtered by Stage 1) ───────────
          AND m.polymer = $polymer

        // ── Range gate: Density ─────────────────────────────────────────────
          AND (f.density_min IS NULL OR $density IS NULL OR f.density_min <= $density)
          AND (f.density_max IS NULL OR $density IS NULL OR f.density_max >= $density)

        // ── Range gate: MFI ─────────────────────────────────────────────────
          AND (f.melt_index_min IS NULL OR $mfi IS NULL OR f.melt_index_min <= $mfi)
          AND (f.melt_index_max IS NULL OR $mfi IS NULL OR f.melt_index_max >= $mfi)

        // ── Equipment gates ─────────────────────────────────────────────────
          AND (NOT $requires_wash_line OR f.has_wash_line = true)
          AND (NOT $requires_dryer OR f.can_reduce_moisture = true)

        // ══════════════════════════════════════════════════════════════════
        // SOFT SIGNALS (scoring, don't exclude)
        // ══════════════════════════════════════════════════════════════════
        WITH f, m,
             CASE WHEN m.form = $form THEN 1 ELSE 0 END AS form_match,
             CASE WHEN m.color = $color THEN 1 ELSE 0 END AS color_match,
             CASE WHEN m.source_type = $source_type THEN 1 ELSE 0 END AS source_match,
             CASE WHEN f.process_type = $origin_process_type THEN 1 ELSE 0 END AS process_match

        // ── Transaction history ─────────────────────────────────────────────
        OPTIONAL MATCH (supplier:Facility {facility_id: $supplier_facility_id})-[tx:TRANSACTED_WITH]->(f)
        WITH f, m, form_match, color_match, source_match, process_match,
             COALESCE(tx.tx_count, 0) AS tx_count

        // ── Geo distance (if coordinates available) ─────────────────────────
        WITH f, m, form_match, color_match, source_match, process_match, tx_count,
             CASE
               WHEN $intake_point IS NOT NULL AND f.location IS NOT NULL
               THEN point.distance(f.location, point($intake_point))
               ELSE 0
             END AS distance_m

        // ══════════════════════════════════════════════════════════════════
        // COMPOSITE SCORING
        // ══════════════════════════════════════════════════════════════════
        WITH f, m, distance_m, tx_count,
             1.0 AS hard_score,  // All hard gates passed
             (form_match * 0.3 + color_match * 0.2 + source_match * 0.3 + process_match * 0.2) AS soft_score,
             CASE
               WHEN $radius_meters > 0 AND distance_m > 0
               THEN 1.0 - (distance_m / $radius_meters)
               ELSE 1.0
             END AS geo_score

        WITH f, m, distance_m, tx_count, hard_score, soft_score, geo_score,
             ($w1 * hard_score
              + $w2 * soft_score
              + $w3 * geo_score
              + $w4 * CASE WHEN tx_count > 0
                           THEN log(1 + tx_count) / log(1 + 100)
                           ELSE 0 END
             ) AS score

        ORDER BY score DESC
        LIMIT $max_results

        RETURN f.facility_id       AS facility_partner_id,
               f.name              AS facility_name,
               f.process_type      AS process_type,
               m.polymer           AS polymer,
               m.form              AS form,
               m.color             AS color,
               round(score * 100) / 100.0 AS score,
               round(distance_m / 1609.34) AS distance_miles,
               tx_count,
               hard_score,
               soft_score,
               geo_score
        """

    def _persist_two_stage_results(self, intake, results):
        """Persist two-stage match results to plasticos.match.result."""
        Match = self.env["plasticos.match.result"].sudo()
        FacilityProfile = self.env["plasticos.facility.profile"].sudo()

        # Clear previous two-stage results
        Match.search([("intake_id", "=", intake.id), ("l9_run_id", "=", "two_stage_v1")]).unlink()

        for rank, row in enumerate(results, start=1):
            partner_id = row.get("facility_partner_id")
            if not partner_id:
                continue

            facility_profile = FacilityProfile.search([("partner_id", "=", partner_id)], limit=1)
            score = row.get("score", 0) * 100

            breakdown = {
                "rank": rank,
                "source": "two_stage_v1",
                "hard_score": round(row.get("hard_score", 0) * 100, 1),
                "soft_score": round(row.get("soft_score", 0) * 100, 1),
                "geo_score": round(row.get("geo_score", 0) * 100, 1),
                "tx_count": row.get("tx_count", 0),
                "stage1_distance_miles": row.get("stage1_distance_miles"),
            }

            reasoning = f"Two-stage #{rank} | polymer={row.get('polymer')}"
            if row.get("distance_miles"):
                reasoning += f" | {row.get('distance_miles'):.0f}mi"
            if row.get("tx_count", 0) > 0:
                reasoning += f" | {row.get('tx_count')} prior tx"

            Match.create(
                {
                    "intake_id": intake.id,
                    "buyer_partner_id": partner_id,
                    "facility_profile_id": facility_profile.id if facility_profile else False,
                    "score": score,
                    "confidence": 100.0,
                    "score_breakdown": breakdown,
                    "match_reasoning": reasoning,
                    "state": "pending",
                    "l9_run_id": "two_stage_v1",
                    "l9_timestamp": fields.Datetime.now(),
                }
            )
