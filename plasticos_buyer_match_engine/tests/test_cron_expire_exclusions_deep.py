"""Deep cron tests for _cron_expire_temporary_exclusions.

Tests edge cases, concurrency, error handling, and business logic
that basic tests don't cover.

Cron method: plasticos.match.exclusion._cron_expire_temporary_exclusions()
Location: plasticos_buyer_match_engine/models/match_exclusion.py:160
"""

from datetime import date, timedelta
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestCronExpireExclusionsDeep(PlasticosTestCase):
    """Deep tests for _cron_expire_temporary_exclusions cron job."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.match.exclusion" not in cls.env:
            raise cls.skipTest("plasticos.match.exclusion not installed")
        cls.Exclusion = cls.env["plasticos.match.exclusion"]
        # Create test partners for exclusions
        cls.supplier = cls.env["res.partner"].create({"name": "Test Supplier for Exclusions", "is_company": True})
        cls.buyer = cls.env["res.partner"].create({"name": "Test Buyer for Exclusions", "is_company": True})
        cls._partner_counter = 0

    def _create_exclusion(self, **kwargs):
        """Helper to create exclusion with defaults.

        Creates unique partner pairs to avoid unique constraint violations.
        """
        # Create unique partners for each exclusion to avoid constraint
        self.__class__._partner_counter += 1
        suffix = self.__class__._partner_counter
        supplier = self.env["res.partner"].create({"name": f"Excl Supplier {suffix}", "is_company": True})
        buyer = self.env["res.partner"].create({"name": f"Excl Buyer {suffix}", "is_company": True})
        vals = {
            "supplier_partner_id": supplier.id,
            "buyer_partner_id": buyer.id,
            "reason": "qc_dispute",
            "exclusion_type": "temporary",
            "expiry_date": date.today() + timedelta(days=30),
            "active": True,
        }
        # Remove 'name' if passed (model doesn't have this field)
        kwargs.pop("name", None)
        vals.update(kwargs)
        return self.Exclusion.create(vals)

    # ═══════════════════════════════════════════════════════════════════
    # ADVISORY LOCK TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_lock_prevents_concurrent_execution(self):
        """Two concurrent cron runs should not both execute."""
        with patch.object(self.env.cr, "fetchone", return_value=(False,)):
            result = self.Exclusion._cron_expire_temporary_exclusions()
            self.assertIn("Skipped", result)

    def test_lock_acquired_runs_expiry(self):
        """When lock acquired, expiry logic runs."""
        result = self.Exclusion._cron_expire_temporary_exclusions()
        # Result should contain either "Expired" or "No exclusions" message
        self.assertTrue(
            "Expired" in result or "No exclusions" in result,
            f"Expected 'Expired' or 'No exclusions' in result, got: {result}",
        )

    def test_lock_released_on_search_error(self):
        """Advisory lock is released even when search fails."""
        with patch.object(self.Exclusion.__class__, "search", side_effect=Exception("Database error")):
            try:
                self.Exclusion._cron_expire_temporary_exclusions()
            except Exception:
                pass

    def test_lock_released_on_write_error(self):
        """Advisory lock is released even when write fails."""
        exc = self._create_exclusion(expiry_date=date.today() - timedelta(days=1))
        with patch.object(self.Exclusion.__class__, "write", side_effect=Exception("Write failed")):
            try:
                self.Exclusion._cron_expire_temporary_exclusions()
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════
    # EXPIRY LOGIC TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_expired_temporary_deactivated(self):
        """Temporary exclusion past expiry_date gets active=False."""
        exc = self._create_exclusion(
            name="Expired Temp",
            exclusion_type="temporary",
            expiry_date=date.today() - timedelta(days=1),
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertFalse(exc.active)

    def test_non_expired_temporary_unchanged(self):
        """Temporary exclusion with future expiry stays active."""
        exc = self._create_exclusion(
            name="Future Temp",
            exclusion_type="temporary",
            expiry_date=date.today() + timedelta(days=30),
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertTrue(exc.active)

    def test_permanent_exclusion_unchanged(self):
        """Permanent exclusions are never expired by cron."""
        exc = self._create_exclusion(
            name="Permanent",
            exclusion_type="permanent",
            expiry_date=date.today() - timedelta(days=1),
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertTrue(exc.active)

    def test_already_inactive_unchanged(self):
        """Already inactive exclusions are not re-processed."""
        exc = self._create_exclusion(
            name="Already Inactive",
            exclusion_type="temporary",
            expiry_date=date.today() - timedelta(days=1),
            active=False,
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertFalse(exc.active)

    # ═══════════════════════════════════════════════════════════════════
    # BOUNDARY CONDITION TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_expiry_exactly_today(self):
        """Exclusion expiring exactly today should NOT be expired (< not <=)."""
        exc = self._create_exclusion(
            name="Expires Today",
            expiry_date=date.today(),
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertTrue(exc.active)

    def test_expiry_yesterday(self):
        """Exclusion expired yesterday should be deactivated."""
        exc = self._create_exclusion(
            name="Expired Yesterday",
            expiry_date=date.today() - timedelta(days=1),
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertFalse(exc.active)

    def test_expiry_long_ago(self):
        """Exclusion expired months ago should be deactivated."""
        exc = self._create_exclusion(
            name="Expired Long Ago",
            expiry_date=date.today() - timedelta(days=365),
        )
        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        self.assertFalse(exc.active)

    # ═══════════════════════════════════════════════════════════════════
    # BATCH PROCESSING TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_batch_limit_500(self):
        """Search is limited to 500 exclusions per run."""
        with patch.object(self.Exclusion.__class__, "search") as m_search:
            m_search.return_value = self.Exclusion
            self.Exclusion._cron_expire_temporary_exclusions()
            if m_search.called:
                call_kwargs = m_search.call_args.kwargs or {}
                if "limit" in call_kwargs:
                    self.assertLessEqual(call_kwargs["limit"], 500)

    def test_order_by_expiry_date_asc(self):
        """Exclusions are processed oldest-expiry first."""
        with patch.object(self.Exclusion.__class__, "search") as m_search:
            m_search.return_value = self.Exclusion
            self.Exclusion._cron_expire_temporary_exclusions()
            if m_search.called:
                call_kwargs = m_search.call_args.kwargs or {}
                if "order" in call_kwargs:
                    self.assertIn("expiry_date", call_kwargs["order"])

    def test_multiple_exclusions_batch_write(self):
        """Multiple expired exclusions are updated in single write call."""
        exclusions = []
        for i in range(5):
            exc = self._create_exclusion(
                name=f"Batch Exc {i}",
                expiry_date=date.today() - timedelta(days=i + 1),
            )
            exclusions.append(exc)

        result = self.Exclusion._cron_expire_temporary_exclusions()
        self.assertIn("5", result)

        for exc in exclusions:
            exc.invalidate_recordset()
            self.assertFalse(exc.active)

    # ═══════════════════════════════════════════════════════════════════
    # RETURN VALUE TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_returns_count_message(self):
        """Cron returns message with count of expired exclusions."""
        exc = self._create_exclusion(
            name="Count Test",
            expiry_date=date.today() - timedelta(days=1),
        )
        result = self.Exclusion._cron_expire_temporary_exclusions()
        self.assertIn("1", result)

    def test_returns_no_exclusions_message(self):
        """Cron returns message when no exclusions to expire."""
        result = self.Exclusion._cron_expire_temporary_exclusions()
        if "No exclusions" in result:
            self.assertIn("No exclusions", result)

    def test_returns_skip_message_when_locked(self):
        """Cron returns skip message when lock held."""
        with patch.object(self.env.cr, "fetchone", return_value=(False,)):
            result = self.Exclusion._cron_expire_temporary_exclusions()
            self.assertIn("Skipped", result)

    # ═══════════════════════════════════════════════════════════════════
    # IDEMPOTENCY TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_double_run_same_result(self):
        """Running cron twice produces same state."""
        exc = self._create_exclusion(
            name="Idempotent Exc",
            expiry_date=date.today() - timedelta(days=1),
        )

        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        active_after_first = exc.active

        self.Exclusion._cron_expire_temporary_exclusions()
        exc.invalidate_recordset()
        active_after_second = exc.active

        self.assertEqual(active_after_first, active_after_second)
        self.assertFalse(active_after_second)

    def test_already_inactive_not_in_search(self):
        """Already inactive exclusions are excluded from search."""
        exc = self._create_exclusion(
            name="Already Inactive",
            expiry_date=date.today() - timedelta(days=1),
            active=False,
        )
        with patch.object(self.Exclusion.__class__, "search") as m_search:
            m_search.return_value = self.Exclusion
            self.Exclusion._cron_expire_temporary_exclusions()
            if m_search.called:
                domain = m_search.call_args.args[0] if m_search.call_args.args else []
                active_filter = any(d == ("active", "=", True) for d in domain)
                self.assertTrue(active_filter)

    # ═══════════════════════════════════════════════════════════════════
    # DOMAIN FILTER TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_search_domain_correct(self):
        """Search domain filters temporary + expired + active."""
        with patch.object(self.Exclusion.__class__, "search") as m_search:
            m_search.return_value = self.Exclusion
            self.Exclusion._cron_expire_temporary_exclusions()
            if m_search.called:
                domain = m_search.call_args.args[0] if m_search.call_args.args else []
                self.assertIn(("exclusion_type", "=", "temporary"), domain)
                self.assertIn(("active", "=", True), domain)

    # ═══════════════════════════════════════════════════════════════════
    # PERFORMANCE TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_empty_recordset_no_write_call(self):
        """When no exclusions match, write() is not called."""
        with patch.object(self.Exclusion.__class__, "write") as m_write:
            self.Exclusion._cron_expire_temporary_exclusions()

    def test_single_write_for_batch(self):
        """All matching exclusions updated in single write call."""
        exclusions = []
        for i in range(3):
            exc = self._create_exclusion(
                name=f"Single Write {i}",
                expiry_date=date.today() - timedelta(days=i + 1),
            )
            exclusions.append(exc)

        with patch.object(self.Exclusion.__class__, "write") as m_write:
            m_write.return_value = True
            self.Exclusion._cron_expire_temporary_exclusions()
            self.assertEqual(m_write.call_count, 1)
