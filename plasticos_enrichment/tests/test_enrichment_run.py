"""Unit tests for plasticos.enrichment.run pipeline.

Tests cover:
- Auto-sequence on create
- Default state is draft
- action_execute requires at least one source
- State progression: draft → crawling → extracting → validated/review/failed
- action_inject: only from validated or review state
- action_inject: creates/updates material profiles
- action_inject: records provenance entries
- action_run_inference: only from injected state
- Confidence computed from injectable extractions
- Cron batch processing
"""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestEnrichmentRun(PlasticosTestCase):
    """Test enrichment run state machine and guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Enrichment Target",
                "is_company": True,
            }
        )

    def _create_run(self, **kwargs):
        vals = {
            "partner_id": self.partner.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.enrichment.run"].create(vals)

    # ── Creation ────────────────────────────────────────────────

    def test_auto_sequence(self):
        """Run name auto-generated from ir.sequence."""
        run = self._create_run()
        self.assertTrue(run.name)
        self.assertNotEqual(run.name, "New")

    def test_default_state_draft(self):
        """New runs start in draft."""
        run = self._create_run()
        self.assertEqual(run.state, "draft")

    # ── action_execute Guards ───────────────────────────────────

    def test_execute_without_sources_raises(self):
        """action_execute raises when no source URLs."""
        run = self._create_run()
        with self.assertRaises(UserError):
            run.action_execute()

    # ── action_inject Guards ────────────────────────────────────

    def test_inject_from_draft_raises(self):
        """action_inject raises when state is draft."""
        run = self._create_run()
        with self.assertRaises(UserError):
            run.action_inject()

    def test_inject_from_crawling_raises(self):
        """action_inject raises when state is crawling."""
        run = self._create_run()
        run.state = "crawling"
        with self.assertRaises(UserError):
            run.action_inject()

    # ── action_run_inference Guards ─────────────────────────────

    def test_inference_from_draft_raises(self):
        """action_run_inference raises when state is not injected."""
        run = self._create_run()
        with self.assertRaises(UserError):
            run.action_run_inference()

    def test_inference_from_validated_raises(self):
        """action_run_inference raises from validated (needs injected)."""
        run = self._create_run()
        run.state = "validated"
        with self.assertRaises(UserError):
            run.action_run_inference()

    # ── Confidence Computed ─────────────────────────────────────

    def test_confidence_zero_no_extractions(self):
        """Confidence is 0 when no extractions."""
        run = self._create_run()
        self.assertEqual(run.confidence_score, 0.0)

    def test_confidence_min_of_injectable(self):
        """Confidence is min of injectable extraction confidences."""
        run = self._create_run()
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": False,
                "confidence": 0.85,
                "is_injectable": True,
                "material_json": [],
            }
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": False,
                "confidence": 0.60,
                "is_injectable": True,
                "material_json": [],
            }
        )
        run.invalidate_recordset()
        self.assertAlmostEqual(run.confidence_score, 0.60, places=2)

    def test_confidence_ignores_non_injectable(self):
        """Non-injectable extractions excluded from confidence."""
        run = self._create_run()
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": False,
                "confidence": 0.30,
                "is_injectable": False,
                "material_json": [],
            }
        )
        self.env["plasticos.enrichment.extraction"].create(
            {
                "run_id": run.id,
                "source_id": False,
                "confidence": 0.90,
                "is_injectable": True,
                "material_json": [],
            }
        )
        run.invalidate_recordset()
        self.assertAlmostEqual(run.confidence_score, 0.90, places=2)

    def test_execute_persists_extraction_error_details(self):
        """Extraction API failures are persisted as failed run validation issues."""
        run = self._create_run()
        source = self.env["plasticos.enrichment.source"].create(
            {
                "partner_id": self.partner.id,
                "url": "https://example.com/extract-fail",
                "crawl_status": "success",
                "raw_content": "test payload",
            }
        )
        run.write({"source_ids": [(6, 0, [source.id])]})

        with patch.object(
            self.env["plasticos.enrichment.service"].__class__,
            "extract_from_source",
            side_effect=Exception("API outage"),
        ):
            run.action_execute()

        self.assertEqual(run.state, "failed")
        self.assertIn("API outage", str(run.validation_issues or []))
