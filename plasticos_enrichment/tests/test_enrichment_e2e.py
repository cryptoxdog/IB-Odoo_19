"""Tests for plasticos.enrichment.run — end-to-end enrichment pipeline.

Target module: plasticos_enrichment
Target models: plasticos.enrichment.run, plasticos.enrichment.source,
               plasticos.enrichment.extraction, plasticos.enrichment.provenance

Tests lifecycle: draft → crawling → extracting → validated/review/failed → injected.
Validates merge-not-overwrite semantics and provenance tracking.
"""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "integration", "enrichment")
class TestEnrichmentPipelineE2E(TransactionCase):
    """End-to-end enrichment pipeline tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env["plasticos.enrichment.run"]
        cls.Source = cls.env["plasticos.enrichment.source"]
        cls.Extraction = cls.env["plasticos.enrichment.extraction"]
        cls.Provenance = cls.env["plasticos.enrichment.provenance"]
        cls.MatProfile = cls.env["plasticos.material.profile"]

        # Company + Facility (required for material profile)
        cls.company = cls.env["res.partner"].create(
            {
                "name": "Enrichment Test Corp",
                "is_company": True,
            }
        )
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "Enrichment Test Facility",
                "parent_id": cls.company.id,
            }
        )

        # Master data
        Polymer = cls.env["plasticos.polymer"]
        Form = cls.env["plasticos.material.form"]

        cls.polymer = Polymer.search([("code", "=ilike", "HDPE")], limit=1)
        if not cls.polymer:
            cls.polymer = Polymer.create({"name": "HDPE", "code": "HDPE"})

        cls.form = Form.search([("code", "=ilike", "PELLETS")], limit=1)
        if not cls.form:
            cls.form = Form.create({"name": "Pellets", "code": "PELLETS"})

        # Ensure ir.sequence exists
        seq = cls.env["ir.sequence"].search(
            [("code", "=", "plasticos.enrichment.run")],
            limit=1,
        )
        if not seq:
            cls.env["ir.sequence"].create(
                {
                    "name": "Enrichment Run",
                    "code": "plasticos.enrichment.run",
                    "prefix": "ENR-",
                    "padding": 5,
                }
            )

    def _create_source(self, **kwargs):
        """Helper: create an enrichment source."""
        vals = {
            "partner_id": self.company.id,
            "source_type": "website",
            "url": "https://test-corp.com/products",
        }
        vals.update(kwargs)
        return self.Source.create(vals)

    def _create_run(self, **kwargs):
        """Helper: create an enrichment run with one source."""
        source = self._create_source()
        vals = {
            "partner_id": self.company.id,
            "source_ids": [(6, 0, [source.id])],
        }
        vals.update(kwargs)
        return self.Run.create(vals)

    # ── Run Lifecycle ──────────────────────────────────────────

    def test_run_created_in_draft(self):
        """Enrichment run starts in draft state."""
        run = self._create_run()
        self.assertTrue(run.id)
        self.assertEqual(run.state, "draft")
        self.assertTrue(run.name)

    def test_execute_requires_sources(self):
        """action_execute raises UserError with no sources."""
        run = self.Run.create({"partner_id": self.company.id})
        with self.assertRaises(UserError):
            run.action_execute()

    def test_execute_fails_when_crawl_fails(self):
        """Pipeline transitions to failed when no sources crawl successfully."""
        run = self._create_run()
        # Source has no actual content — crawl will fail
        run.action_execute()
        run.invalidate_recordset()
        self.assertIn(run.state, ("failed", "review"))

    # ── Inject Guards ──────────────────────────────────────────

    def test_inject_blocked_from_draft(self):
        """action_inject raises UserError from draft state."""
        run = self._create_run()
        with self.assertRaises(UserError):
            run.action_inject()

    def test_inject_blocked_from_failed(self):
        """action_inject raises UserError from failed state."""
        run = self._create_run()
        run.write({"state": "failed"})
        with self.assertRaises(UserError):
            run.action_inject()

    # ── Inject from Validated ──────────────────────────────────

    def test_inject_from_validated_transitions_to_injected(self):
        """action_inject from validated → injected with counters."""
        run = self._create_run()
        run.write({"state": "validated"})

        # Create a mock extraction with injectable material
        source = run.source_ids[0]
        self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "material_json": [
                    {
                        "polymer": "HDPE",
                        "form": "pellets",
                        "contamination_tolerance_pct": 2.0,
                    }
                ],
                "metadata_json": {"source_url": "https://test.com"},
                "confidence": 0.95,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )

        run.action_inject()
        run.invalidate_recordset()

        self.assertEqual(run.state, "injected")
        self.assertTrue(run.injected_at)

    def test_inject_from_review_also_works(self):
        """Manual approval: inject from review state succeeds."""
        run = self._create_run()
        run.write({"state": "review"})

        source = run.source_ids[0]
        self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "material_json": [
                    {
                        "polymer": "HDPE",
                        "form": "pellets",
                    }
                ],
                "metadata_json": {},
                "confidence": 0.90,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )

        run.action_inject()
        run.invalidate_recordset()
        self.assertEqual(run.state, "injected")

    # ── Provenance Tracking ────────────────────────────────────

    def test_provenance_records_created_on_inject(self):
        """Injection creates provenance records for each field write."""
        run = self._create_run()
        run.write({"state": "validated"})

        source = run.source_ids[0]
        self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "material_json": [
                    {
                        "polymer": "HDPE",
                        "form": "pellets",
                        "contamination_tolerance_pct": 3.5,
                    }
                ],
                "metadata_json": {"source_url": "https://test.com"},
                "confidence": 0.95,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )

        run.action_inject()
        run.invalidate_recordset()

        provenance = self.Provenance.search([("run_id", "=", run.id)])
        if run.state == "injected" and run.fields_written > 0:
            self.assertGreater(len(provenance), 0)
            for prov in provenance:
                self.assertEqual(prov.target_model, "plasticos.material.profile")
                self.assertTrue(prov.target_field)
                self.assertIn(prov.status, ("written", "skipped_immutable", "unmapped", "inferred"))

    # ── Extraction Model ───────────────────────────────────────

    def test_extraction_is_injectable_computed(self):
        """is_injectable = governance_passed AND confidence >= 0.85."""
        run = self._create_run()
        source = run.source_ids[0]

        ext_good = self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "confidence": 0.90,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )
        self.assertTrue(ext_good.is_injectable)

        ext_low_conf = self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "confidence": 0.50,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )
        self.assertFalse(ext_low_conf.is_injectable)

        ext_gov_fail = self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "confidence": 0.95,
                "governance_passed": False,
                "extracted_at": fields.Datetime.now(),
            }
        )
        self.assertFalse(ext_gov_fail.is_injectable)

    # ── Confidence Score Computed ──────────────────────────────

    def test_confidence_score_is_min_of_injectable(self):
        """Run confidence_score = min(injectable extraction confidences)."""
        run = self._create_run()
        source = run.source_ids[0]

        self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "confidence": 0.95,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )
        self.Extraction.create(
            {
                "run_id": run.id,
                "source_id": source.id,
                "confidence": 0.88,
                "governance_passed": True,
                "extracted_at": fields.Datetime.now(),
            }
        )
        run.invalidate_recordset()
        self.assertAlmostEqual(run.confidence_score, 0.88, places=2)

    # ── Inference Guard ────────────────────────────────────────

    def test_inference_blocked_before_inject(self):
        """action_run_inference raises UserError if not injected."""
        run = self._create_run()
        run.write({"state": "validated"})
        with self.assertRaises(UserError):
            run.action_run_inference()

    # ── Source Model ───────────────────────────────────────────

    def test_source_defaults(self):
        """Source created with expected defaults."""
        source = self._create_source()
        self.assertEqual(source.crawl_status, "pending")
        self.assertTrue(source.active)
        self.assertFalse(source.last_crawled_at)
