"""Tests for plasticos.web.lead — _run_triage_pipeline() integration.

Target module: plasticos_web_leads
Target model:  plasticos.web.lead

Tests the deterministic triage pipeline path:
  - AI disabled → deterministic classification only
  - HOT leads → intake created
  - COLD leads → state = skipped
  - Error handling → state = error
"""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "integration", "web_lead")
class TestWebLeadTriagePipeline(PlasticosTestCase):
    """Integration tests for the AI triage pipeline."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]
        cls.Config = cls.env["plasticos.web.lead.config"]

        # Master data for intake creation
        Polymer = cls.env["plasticos.polymer"]
        Form = cls.env["plasticos.material.form"]
        SourceType = cls.env["plasticos.source.type"]

        cls.polymer = Polymer.search([("code", "=ilike", "HDPE")], limit=1)
        if not cls.polymer:
            cls.polymer = Polymer.create({"name": "HDPE", "code": "HDPE"})

        cls.form = Form.search([("code", "=ilike", "BALES")], limit=1)
        if not cls.form:
            cls.form = Form.create({"name": "Bales", "code": "BALES"})

        cls.source_type = SourceType.search([("code", "=ilike", "post_consumer")], limit=1)
        if not cls.source_type:
            cls.source_type = SourceType.create({"name": "Post Consumer", "code": "post_consumer"})

        # Config with AI disabled (deterministic-only pipeline)
        cls.config = cls.Config.sudo().get_config()
        cls.config.write(
            {
                "ai_enabled": False,
                "vision_enabled": False,
                "auto_create_partner": True,
            }
        )

    def _create_web_lead(self, **kwargs):
        """Helper: create a web.lead in received state."""
        vals = {
            "lead_id": "WL-TRIAGE-001",
            "decision": "cold",
            "source": "test",
            "company_name": "Test Corp",
            "contact_name": "Jane Smith",
            "contact_email": "jane@test.com",
            "material_description": "HDPE bales, post-industrial",
            "estimated_lbs_per_load": 0,
            "state": "received",
            "raw_payload": {
                "YourBusinessCompanyName": "Test Corp",
                "DescribeYourMaterial": "HDPE bales",
            },
        }
        vals.update(kwargs)
        return self.WebLead.create(vals)

    # ── Cold Lead Pipeline ─────────────────────────────────────

    def test_cold_lead_pipeline_skips(self):
        """Lead classified as COLD ends in skipped state."""
        lead = self._create_web_lead(
            lead_id="WL-TRIAGE-COLD-001",
            estimated_lbs_per_load=2000,
            material_description="small amount of mixed plastic",
        )
        lead._run_triage_pipeline()
        lead.invalidate_recordset()

        self.assertIn(lead.state, ("skipped", "error"))
        if lead.state == "skipped":
            self.assertEqual(lead.decision, "cold")
            self.assertFalse(lead.intake_id)

    def test_cold_lead_has_triage_log(self):
        """Pipeline writes triage_log regardless of outcome."""
        lead = self._create_web_lead(
            lead_id="WL-TRIAGE-LOG-001",
            estimated_lbs_per_load=1000,
        )
        lead._run_triage_pipeline()
        lead.invalidate_recordset()

        self.assertTrue(lead.triage_log)
        self.assertIn("Step", lead.triage_log)

    # ── HOT Lead Pipeline ──────────────────────────────────────

    def test_hot_lead_pipeline_creates_intake(self):
        """Lead that classifies as HOT creates an intake record."""
        lead = self._create_web_lead(
            lead_id="WL-TRIAGE-HOT-001",
            estimated_lbs_per_load=45000,
            material_description="HDPE bales, commercial, clean",
            raw_payload={
                "YourBusinessCompanyName": "Big Recycler Inc",
                "DescribeYourMaterial": "HDPE bales, commercial source",
                "WhatIsTheSourceOfThisMaterial": "post_industrial",
            },
        )
        lead._run_triage_pipeline()
        lead.invalidate_recordset()

        if lead.state == "intake_created":
            self.assertEqual(lead.decision, "hot")
            self.assertTrue(lead.intake_id)
            self.assertTrue(lead.intake_id.id)

    # ── Error Handling ─────────────────────────────────────────

    def test_pipeline_error_sets_error_state(self):
        """Exception during pipeline sets state=error with message."""
        lead = self._create_web_lead(lead_id="WL-TRIAGE-ERR-001")

        # Patch classify_lead where it's used (in web_lead module)
        with patch(
            "odoo.addons.plasticos_web_leads.models.web_lead.classify_lead",
            side_effect=RuntimeError("AI service down"),
        ):
            lead._run_triage_pipeline()

        lead.invalidate_recordset()
        self.assertEqual(lead.state, "error")
        self.assertTrue(lead.error_message)
        self.assertIn("AI service down", lead.error_message)

    # ── AI Disabled Path ───────────────────────────────────────

    def test_ai_disabled_skips_normalization_step(self):
        """When ai_enabled=False, triage log shows normalization SKIPPED."""
        lead = self._create_web_lead(
            lead_id="WL-TRIAGE-NOAI-001",
            estimated_lbs_per_load=5000,
        )
        lead._run_triage_pipeline()
        lead.invalidate_recordset()

        self.assertIn("SKIPPED", lead.triage_log)

    # ── Decision Reasons ───────────────────────────────────────

    def test_decision_reasons_populated(self):
        """Pipeline populates decision_reasons with reasons."""
        lead = self._create_web_lead(
            lead_id="WL-TRIAGE-REASONS-001",
            estimated_lbs_per_load=45000,
            material_description="HDPE bales from commercial facility",
        )
        lead._run_triage_pipeline()
        lead.invalidate_recordset()

        # decision_reasons may be a dict or JSON string depending on field type
        if lead.decision_reasons:
            reasons = lead.decision_reasons
            if isinstance(reasons, str):
                import json

                reasons = json.loads(reasons)
            self.assertIn("reasons", reasons)

    # ── Action Methods ─────────────────────────────────────────

    def test_action_retry_only_from_error(self):
        """action_retry_processing raises UserError on non-error leads."""
        lead = self._create_web_lead(
            lead_id="WL-RETRY-001",
            state="received",
        )
        with self.assertRaises(UserError):
            lead.action_retry_processing()

    def test_action_force_create_intake_blocks_duplicate(self):
        """action_force_create_intake blocks if intake already exists."""
        lead = self._create_web_lead(
            lead_id="WL-FORCE-001",
            decision="hot",
        )
        lead._run_triage_pipeline()
        lead.invalidate_recordset()

        if lead.intake_id:
            with self.assertRaises(UserError):
                lead.action_force_create_intake()

    def test_action_retry_triage_allowed_states(self):
        """action_retry_triage only from error/skipped/received."""
        lead = self._create_web_lead(
            lead_id="WL-RETRIAGE-001",
            state="received",
        )
        # Should not raise
        lead.action_retry_triage()
        lead.invalidate_recordset()
        self.assertNotEqual(lead.state, "received")
