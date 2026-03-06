"""Tests for plasticos.graph.service — sync orchestration and graceful degradation.

Target module: plasticos_buyer_match_engine
Target model:  plasticos.graph.service (AbstractModel)

Tests sync pipeline phases, sync log creation, and graceful behavior
when Neo4j is NOT configured (all _execute_cypher calls return []).
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "integration", "graph")
class TestGraphServiceSync(PlasticosTestCase):
    """Test graph sync orchestration without live Neo4j."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.GraphSvc = cls.env["plasticos.graph.service"]
        cls.SyncLog = cls.env["plasticos.graph.sync.log"]

        # Ensure Neo4j is NOT configured (graceful degradation mode)
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("plasticos_graph.neo4j_uri", "")
        ICP.set_param("plasticos_graph.neo4j_user", "")
        ICP.set_param("plasticos_graph.neo4j_password", "")

    # ── Config ─────────────────────────────────────────────────

    def test_get_config_returns_dict(self):
        """_get_config() always returns a dict with expected keys."""
        config = self.GraphSvc._get_config()
        self.assertIsInstance(config, dict)
        self.assertIn("uri", config)
        self.assertIn("user", config)
        self.assertIn("password", config)
        self.assertIn("pool_size", config)
        self.assertIn("max_distance_km", config)

    def test_get_scoring_weights_returns_four_dimensions(self):
        """_get_scoring_weights() returns 4 scoring dimensions."""
        weights = self.GraphSvc._get_scoring_weights()
        self.assertIn("hard_gate", weights)
        self.assertIn("quality", weights)
        self.assertIn("geo", weights)
        self.assertIn("history", weights)
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=2)

    # ── Graceful Degradation ───────────────────────────────────

    def test_execute_cypher_returns_empty_when_unconfigured(self):
        """_execute_cypher() returns [] when Neo4j not configured."""
        result = self.GraphSvc._execute_cypher("RETURN 1 AS n")
        self.assertEqual(result, [])

    def test_get_driver_returns_none_when_unconfigured(self):
        """_get_driver() returns None without Neo4j password."""
        driver = self.GraphSvc._get_driver()
        self.assertIsNone(driver)

    def test_get_pool_raises_when_unconfigured(self):
        """_get_pool() raises UserError without Neo4j config."""
        with self.assertRaises(UserError):
            self.GraphSvc._get_pool()

    # ── Sync Creates Logs ──────────────────────────────────────

    def test_sync_facility_creates_log(self):
        """sync_facility_nodes creates a sync log entry."""
        log_before = self.SyncLog.search_count([("sync_type", "=", "facility")])
        self.GraphSvc.sync_facility_nodes(trigger="test")
        log_after = self.SyncLog.search_count([("sync_type", "=", "facility")])
        self.assertGreater(log_after, log_before)

    def test_sync_material_creates_log(self):
        """sync_material_nodes creates a sync log entry."""
        log_before = self.SyncLog.search_count([("sync_type", "=", "material")])
        self.GraphSvc.sync_material_nodes(trigger="test")
        log_after = self.SyncLog.search_count([("sync_type", "=", "material")])
        self.assertGreater(log_after, log_before)

    def test_sync_all_creates_full_log(self):
        """sync_all() creates a 'full' sync log entry."""
        log_before = self.SyncLog.search_count([("sync_type", "=", "full")])
        self.GraphSvc.sync_all(trigger="test")
        log_after = self.SyncLog.search_count([("sync_type", "=", "full")])
        self.assertGreater(log_after, log_before)

    def test_sync_all_runs_all_phases_without_error(self):
        """sync_all() completes all 7 phases gracefully without Neo4j."""
        self.GraphSvc.sync_all(trigger="test")
        logs = self.SyncLog.search([], order="id desc", limit=10)
        log_types = logs.mapped("sync_type")
        self.assertIn("full", log_types)

    # ── Payload Builders ───────────────────────────────────────

    def test_build_facility_payloads_returns_list(self):
        """_build_facility_payloads() returns a list (possibly empty)."""
        payloads = self.GraphSvc._build_facility_payloads()
        self.assertIsInstance(payloads, list)

    def test_build_material_payloads_returns_list(self):
        """_build_material_payloads() returns a list (possibly empty)."""
        payloads = self.GraphSvc._build_material_payloads()
        self.assertIsInstance(payloads, list)

    # ── Connection Test Action ─────────────────────────────────

    def test_action_test_connection_returns_failure_dict(self):
        """action_test_neo4j_connection returns failure when unconfigured."""
        result = self.GraphSvc.action_test_neo4j_connection()
        self.assertIsInstance(result, dict)
        self.assertFalse(result["success"])
        self.assertIn("not configured", result["message"].lower())

    # ── Calculate Match Score Graceful ─────────────────────────

    def test_calculate_match_score_returns_zero_when_unconfigured(self):
        """calculate_match_score returns 0.0 total_score without Neo4j."""
        result = self.GraphSvc.calculate_match_score(
            supplier_partner_id=999,
            buyer_partner_id=998,
            material_requirements={"polymer_code": "HDPE", "quantity_available": 40000},
        )
        self.assertEqual(result.get("total_score", 0.0), 0.0)
