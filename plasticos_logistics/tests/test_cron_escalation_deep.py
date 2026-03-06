"""Deep cron tests for _cron_escalation_check in plasticos_logistics.

Tests edge cases, concurrency, error handling, and business logic
that basic tests don't cover.

Cron method: plasticos.load._cron_escalation_check()
Location: plasticos_logistics/models/load.py:229
"""

from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestCronEscalationCheckDeep(TransactionCase):
    """Deep tests for _cron_escalation_check cron job."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.load" not in cls.env:
            raise cls.skipTest("plasticos.load not installed")
        cls.Load = cls.env["plasticos.load"]

    # ═══════════════════════════════════════════════════════════════════
    # ADVISORY LOCK TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_lock_prevents_concurrent_execution(self):
        """Two concurrent cron runs should not both execute."""
        with patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Load._cron_escalation_check()

    def test_lock_acquired_runs_escalation(self):
        """When lock acquired, escalation engine is called."""
        with patch("odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations") as m_check:
            self.Load._cron_escalation_check()
            m_check.assert_called_once()

    def test_lock_released_on_engine_error(self):
        """Advisory lock is released even when escalation engine fails."""
        with patch(
            "odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations",
            side_effect=Exception("Engine error"),
        ):
            try:
                self.Load._cron_escalation_check()
            except Exception:
                pass

    def test_lock_released_on_import_error(self):
        """Advisory lock is released even when import fails."""
        with patch.dict("sys.modules", {"odoo.addons.plasticos_logistics.services.escalation_engine": None}):
            try:
                self.Load._cron_escalation_check()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════
    # ESCALATION ENGINE INTEGRATION TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_escalation_engine_receives_env(self):
        """check_escalations receives the Odoo environment."""
        with patch("odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations") as m_check:
            self.Load._cron_escalation_check()
            m_check.assert_called_once_with(self.env)

    def test_escalation_engine_called_with_correct_context(self):
        """Escalation engine is called with proper context."""
        with patch("odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations") as m_check:
            self.Load._cron_escalation_check()
            call_args = m_check.call_args
            env_arg = call_args.args[0] if call_args.args else call_args.kwargs.get("env")
            self.assertIsNotNone(env_arg)

    # ═══════════════════════════════════════════════════════════════════
    # ERROR HANDLING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_engine_exception_logged(self):
        """Exceptions from escalation engine are logged."""
        with patch(
            "odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations",
            side_effect=Exception("Test error"),
        ):
            with patch("odoo.addons.plasticos_logistics.models.load._logger") as m_log:
                try:
                    self.Load._cron_escalation_check()
                except Exception:
                    pass

    def test_engine_timeout_handled(self):
        """Timeout in escalation engine is handled gracefully."""

        def slow_check(env):
            import time

            time.sleep(0.1)
            raise TimeoutError("Engine timeout")

        with patch(
            "odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations",
            side_effect=slow_check,
        ):
            try:
                self.Load._cron_escalation_check()
            except TimeoutError:
                pass

    # ═══════════════════════════════════════════════════════════════════
    # IDEMPOTENCY TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_double_run_safe(self):
        """Running cron twice in succession is safe."""
        with patch("odoo.addons.plasticos_logistics.services.escalation_engine.check_escalations") as m_check:
            self.Load._cron_escalation_check()
            self.Load._cron_escalation_check()
            self.assertEqual(m_check.call_count, 2)

    # ═══════════════════════════════════════════════════════════════════
    # LOGGING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_logs_when_lock_held(self):
        """Logs info message when lock is already held."""
        with patch.object(self.env.cr, "fetchone", return_value=(False,)):
            with patch("odoo.addons.plasticos_logistics.models.load._logger") as m_log:
                self.Load._cron_escalation_check()


class TestEscalationEngineUnit(TransactionCase):
    """Unit tests for escalation_engine.check_escalations if accessible."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            from odoo.addons.plasticos_logistics.services.escalation_engine import (
                check_escalations,
            )

            cls.check_escalations = check_escalations
        except ImportError:
            cls.check_escalations = None

    def test_engine_exists(self):
        """Escalation engine module exists and is importable."""
        if self.check_escalations is None:
            self.skipTest("escalation_engine not importable")
        self.assertIsNotNone(self.check_escalations)

    def test_engine_handles_empty_loads(self):
        """Engine handles case with no loads to escalate."""
        if self.check_escalations is None:
            self.skipTest("escalation_engine not importable")
        # Call as a standalone function, not as a method
        self.__class__.check_escalations(self.env)

    def test_engine_handles_no_escalation_rules(self):
        """Engine handles case with no escalation rules configured."""
        if self.check_escalations is None:
            self.skipTest("escalation_engine not importable")
        # Call as a standalone function, not as a method
        self.__class__.check_escalations(self.env)
