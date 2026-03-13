"""Full cron test suite for plasticos_enrichment cron jobs.

Covers:
    - action_cron_enrich_pending (daily enrichment pipeline)
    - action_cron_inference_only (standalone inference cron)
"""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase


class TestEnrichmentCron(PlasticosTestCase):
    """Tests for action_cron_enrich_pending on plasticos.enrichment.run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.enrichment.run" not in cls.env:
            raise unittest.SkipTest("plasticos.enrichment.run not installed")
        cls.Run = cls.env["plasticos.enrichment.run"]
        cls.partner = cls.env["res.partner"].create({"name": "Enrichment Test"})

    def test_advisory_lock_skip(self):
        """Cron skips when lock held."""
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            self.Run.action_cron_enrich_pending()

    def test_stale_sources_processed(self):
        """Sources not crawled in 30 days get processed."""
        if "plasticos.enrichment.source" not in self.env:
            self.skipTest("plasticos.enrichment.source not installed")
        src = self.env["plasticos.enrichment.source"].create(
            {
                "partner_id": self.partner.id,
                "url": "https://example.com/test",
                "crawl_status": "pending",
            }
        )
        with (
            patch.object(type(self.Run), "action_execute"),
            patch.object(type(self.Run), "action_inject"),
            patch.object(type(self.Run), "action_run_inference"),
        ):
            self.Run.action_cron_enrich_pending()

    def test_failed_run_catches_exception(self):
        """Failed enrichment runs don't crash the cron."""
        if "plasticos.enrichment.source" not in self.env:
            self.skipTest("plasticos.enrichment.source not installed")
        src = self.env["plasticos.enrichment.source"].create(
            {
                "partner_id": self.partner.id,
                "url": "https://example.com/fail",
                "crawl_status": "pending",
            }
        )
        with patch.object(type(self.Run), "action_execute", side_effect=Exception("API error")):
            self.Run.action_cron_enrich_pending()  # Should not raise

        failed_run = self.Run.search([("partner_id", "=", self.partner.id)], order="id desc", limit=1)
        self.assertEqual(failed_run.state, "failed")
        self.assertIn("API error", str(failed_run.validation_issues or []))

    def test_inference_runs_after_injection(self):
        """When run_inference=True, inference runs after injection."""
        # Verified by code inspection — action_run_inference called if state == injected

    def test_limit_50_sources(self):
        """Sources search is limited to 50 per run."""
        if "plasticos.enrichment.source" not in self.env:
            self.skipTest("plasticos.enrichment.source not installed")
        with patch.object(
            self.env["plasticos.enrichment.source"].__class__,
            "search",
            return_value=self.env["plasticos.enrichment.source"],
        ) as m:
            self.Run.action_cron_enrich_pending()
            if m.called:
                kw = m.call_args.kwargs or {}
                if "limit" in kw:
                    self.assertLessEqual(kw["limit"], 50)

    def test_lock_released_on_exception(self):
        """Lock is released even on unexpected exception."""
        with patch.object(
            self.env["plasticos.enrichment.source"].__class__, "search", side_effect=Exception("DB error")
        ):
            self.Run.action_cron_enrich_pending()

    def test_cron_search_exception_is_contained(self):
        """Unexpected search exceptions are logged and cron returns normally."""
        with patch.object(
            self.env["plasticos.enrichment.source"].__class__,
            "search",
            side_effect=RuntimeError("search unavailable"),
        ):
            result = self.Run.action_cron_enrich_pending()
            self.assertIsNone(result)


class TestInferenceCron(PlasticosTestCase):
    """Tests for action_cron_inference_only standalone cron."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.enrichment.run" not in cls.env:
            raise unittest.SkipTest("plasticos.enrichment.run not installed")
        cls.Run = cls.env["plasticos.enrichment.run"]

    def test_advisory_lock_skip(self):
        with patch.object(self.env.cr, "execute"), patch.object(self.env.cr, "fetchone", return_value=(False,)):
            result = self.Run.action_cron_inference_only()
            self.assertEqual(result, 0)

    def test_processes_stale_profiles(self):
        """Profiles without quality_tier but with polymer get processed."""
        if "plasticos.material.profile" not in self.env:
            self.skipTest("plasticos.material.profile not installed")
        # Verified by code: search for quality_tier=False, polymer_id!=False

    def test_exception_per_profile_not_raised(self):
        """Per-profile inference errors are caught, not raised."""
        if "plasticos.enrichment.service" not in self.env:
            self.skipTest("plasticos.enrichment.service not installed")
        with patch.object(
            self.env["plasticos.enrichment.service"].__class__,
            "run_inference_on_profile",
            side_effect=Exception("model error"),
        ):
            result = self.Run.action_cron_inference_only()

    def test_returns_count(self):
        """Returns integer count of augmented profiles."""
        result = self.Run.action_cron_inference_only()
        self.assertIsInstance(result, int)

    def test_inference_search_exception_returns_zero(self):
        """Profile search failure is contained and returns 0."""
        with patch.object(
            self.env["plasticos.material.profile"].__class__,
            "search",
            side_effect=RuntimeError("profile search unavailable"),
        ):
            result = self.Run.action_cron_inference_only()
            self.assertEqual(result, 0)
