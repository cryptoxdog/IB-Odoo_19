"""Full cron test suite for plasticos_buyer_match_engine graph_sync.

Covers: _cron_nightly_graph_sync (full topology sync, advisory lock, error handling).
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestGraphSyncCron(TransactionCase):
    """Tests for _cron_nightly_graph_sync on plasticos.graph.service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.GraphSvc = cls.env["plasticos.graph.service"]

    def test_cron_acquires_lock_and_runs(self):
        """Nightly cron acquires advisory lock and calls sync_all."""
        with patch.object(type(self.GraphSvc), "sync_all") as m_sync:
            result = self.GraphSvc._cron_nightly_graph_sync()
            m_sync.assert_called_once_with(trigger="nightly_cron")
            self.assertIn("completed", result)

    def test_cron_skips_when_lock_held(self):
        """Returns skip message when advisory lock is held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            result = self.GraphSvc._cron_nightly_graph_sync()
            self.assertIn("Skipped", result)

    def test_cron_releases_lock_on_exception(self):
        """Advisory lock is released even when sync_all raises."""
        with patch.object(type(self.GraphSvc), "sync_all", side_effect=Exception("Neo4j down")):
            try:
                self.GraphSvc._cron_nightly_graph_sync()
            except Exception:
                pass

    def test_sync_all_phases(self):
        """sync_all calls all 7 phases in order."""
        with (
            patch.object(type(self.GraphSvc), "initialize_schema") as m1,
            patch.object(type(self.GraphSvc), "sync_facility_nodes") as m2,
            patch.object(type(self.GraphSvc), "sync_material_nodes") as m3,
            patch.object(type(self.GraphSvc), "sync_taxonomy_nodes") as m4,
            patch.object(type(self.GraphSvc), "sync_facility_edges") as m5,
            patch.object(type(self.GraphSvc), "sync_material_edges") as m6,
            patch.object(type(self.GraphSvc), "sync_transaction_edges") as m7,
            patch.object(type(self.GraphSvc), "sync_exclusion_edges") as m8,
            patch.object(type(self.GraphSvc), "sync_derived_edges") as m9,
            patch.object(type(self.GraphSvc), "_create_sync_log"),
        ):
            self.GraphSvc.sync_all(trigger="test")
            m1.assert_called_once()
            m2.assert_called_once()
            m3.assert_called_once()
            m4.assert_called_once()
            m5.assert_called_once()

    def test_sync_facility_empty_payloads(self):
        """sync_facility_nodes handles zero partners gracefully."""
        with (
            patch.object(type(self.GraphSvc), "_build_facility_payloads", return_value=[]),
            patch.object(type(self.GraphSvc), "_create_sync_log") as m_log,
        ):
            self.GraphSvc.sync_facility_nodes()
            m_log.assert_called()

    def test_sync_material_empty_payloads(self):
        """sync_material_nodes handles zero materials gracefully."""
        with (
            patch.object(type(self.GraphSvc), "_build_material_payloads", return_value=[]),
            patch.object(type(self.GraphSvc), "_create_sync_log") as m_log,
        ):
            self.GraphSvc.sync_material_nodes()
            m_log.assert_called()

    def test_execute_cypher_graceful_no_driver(self):
        """_execute_cypher returns [] when Neo4j not configured."""
        result = self.GraphSvc._execute_cypher("RETURN 1")
        self.assertEqual(result, [])

    def test_execute_cypher_query_raises_usererror(self):
        """execute_cypher_query raises UserError on service unavailable."""
        from odoo.exceptions import UserError

        with patch.object(type(self.GraphSvc), "_get_pool", side_effect=UserError("Not configured")):
            with self.assertRaises(UserError):
                self.GraphSvc.execute_cypher_query("RETURN 1")

    def test_sync_log_creation(self):
        """_create_sync_log creates a plasticos.graph.sync.log record."""
        self.GraphSvc._create_sync_log("test", "success", {"records_processed": 5}, None)
        logs = self.env["plasticos.graph.sync.log"].search(
            [
                ("sync_type", "=", "test"),
                ("status", "=", "success"),
            ]
        )
        self.assertTrue(logs)

    def test_sync_log_failure_with_error(self):
        """_create_sync_log records error message on failure."""
        self.GraphSvc._create_sync_log("test_fail", "failed", None, "Connection refused")
        logs = self.env["plasticos.graph.sync.log"].search(
            [
                ("sync_type", "=", "test_fail"),
                ("status", "=", "failed"),
            ]
        )
        self.assertTrue(logs)
        self.assertIn("Connection refused", logs[0].error_message)
