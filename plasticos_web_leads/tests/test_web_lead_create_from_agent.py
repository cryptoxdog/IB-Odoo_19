"""Tests for plasticos.web.lead — create_from_agent() API contract.

Target module: plasticos_web_leads
Target model:  plasticos.web.lead

Validates the external agent ingestion API: payload schema, required
fields, error handling, idempotency, and HOT/COLD routing.
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "contract", "web_lead")
class TestWebLeadCreateFromAgent(TransactionCase):
    """Contract tests for create_from_agent() API endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]

        # Master data needed for HOT-lead intake creation
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

        # Ensure web lead config exists
        Config = cls.env["plasticos.web.lead.config"]
        cls.config = Config.search([], limit=1)
        if not cls.config:
            cls.config = Config.create(
                {
                    "name": "Test Config",
                    "ai_enabled": False,
                    "vision_enabled": False,
                    "auto_create_partner": True,
                }
            )

    def _build_payload(self, **overrides):
        """Helper: build a valid agent payload with sensible defaults."""
        payload = {
            "lead_id": "WL-TEST-001",
            "source": "cognito_form",
            "decision": "Cold",
            "decision_reasons": ["test_reason"],
            "raw_payload": {
                "YourBusinessCompanyName": "Acme Plastics",
                "YourName": "John Doe",
                "Email": "john@acme.com",
                "Phone": "555-0100",
                "DescribeYourMaterial": "HDPE bales, post-consumer",
                "WhatIsTheQuantity": "40000 lbs",
                "AreThereAnyContaminants": "",
            },
            "ai_analysis": {
                "material": {"polymer": "hdpe", "form": "bales"},
                "quantity": {"per_load_lbs": 40000, "loads_per_month": 2},
                "frequency": {"frequency": "monthly"},
            },
        }
        payload.update(overrides)
        return payload

    # ── Required Field Validation ──────────────────────────────

    def test_missing_lead_id_raises_user_error(self):
        """Payload without lead_id raises UserError."""
        payload = self._build_payload()
        del payload["lead_id"]
        with self.assertRaises(UserError):
            self.WebLead.create_from_agent(payload)

    def test_empty_lead_id_raises_user_error(self):
        """Payload with empty string lead_id raises UserError."""
        payload = self._build_payload(lead_id="")
        with self.assertRaises(UserError):
            self.WebLead.create_from_agent(payload)

    # ── Valid COLD Lead ────────────────────────────────────────

    def test_cold_lead_created_with_correct_fields(self):
        """Valid COLD payload creates record with mapped fields."""
        payload = self._build_payload(lead_id="WL-COLD-001", decision="Cold")
        lead = self.WebLead.create_from_agent(payload)

        self.assertTrue(lead.id)
        self.assertEqual(lead.lead_id, "WL-COLD-001")
        self.assertEqual(lead.decision, "cold")
        self.assertEqual(lead.company_name, "Acme Plastics")
        self.assertEqual(lead.contact_name, "John Doe")
        self.assertEqual(lead.contact_email, "john@acme.com")
        self.assertEqual(lead.state, "skipped")

    def test_cold_lead_does_not_create_intake(self):
        """COLD lead should NOT generate an intake record."""
        payload = self._build_payload(lead_id="WL-COLD-002", decision="Cold")
        lead = self.WebLead.create_from_agent(payload)

        self.assertFalse(lead.intake_id)

    # ── Valid HOT Lead ─────────────────────────────────────────

    def test_hot_lead_creates_intake(self):
        """HOT payload creates intake and sets state to intake_created."""
        payload = self._build_payload(lead_id="WL-HOT-001", decision="Hot")
        lead = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead.decision, "hot")
        self.assertIn(lead.state, ("intake_created", "error"))
        if lead.state == "intake_created":
            self.assertTrue(lead.intake_id)
            self.assertTrue(lead.intake_id.id)

    # ── Idempotency ────────────────────────────────────────────

    def test_duplicate_lead_id_returns_existing(self):
        """Second call with same lead_id returns existing record."""
        payload = self._build_payload(lead_id="WL-IDEM-001", decision="Cold")
        lead_1 = self.WebLead.create_from_agent(payload)
        lead_2 = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead_1.id, lead_2.id)

    def test_idempotency_does_not_change_original(self):
        """Duplicate call doesn't mutate the original record's fields."""
        payload = self._build_payload(lead_id="WL-IDEM-002", decision="Cold")
        lead_1 = self.WebLead.create_from_agent(payload)
        original_state = lead_1.state

        payload["decision"] = "Hot"
        lead_2 = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead_2.state, original_state)

    # ── AI Analysis Mapping ────────────────────────────────────

    def test_ai_quantity_fields_mapped(self):
        """AI analysis quantity fields map to integer fields."""
        payload = self._build_payload(lead_id="WL-QTY-001")
        payload["ai_analysis"]["quantity"] = {
            "per_load_lbs": 42000,
            "loads_per_month": 4,
        }
        lead = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead.estimated_lbs_per_load, 42000)
        self.assertEqual(lead.estimated_loads_per_month, 4)

    def test_ai_quantity_handles_non_numeric(self):
        """Non-numeric quantity values default to 0."""
        payload = self._build_payload(lead_id="WL-QTY-002")
        payload["ai_analysis"]["quantity"] = {
            "per_load_lbs": "lots",
            "loads_per_month": None,
        }
        lead = self.WebLead.create_from_agent(payload)

        self.assertEqual(lead.estimated_lbs_per_load, 0)
        self.assertEqual(lead.estimated_loads_per_month, 0)

    # ── Missing Optional Sections ──────────────────────────────

    def test_missing_ai_analysis_defaults_gracefully(self):
        """Payload without ai_analysis still creates valid record."""
        payload = self._build_payload(lead_id="WL-NOAI-001")
        del payload["ai_analysis"]
        lead = self.WebLead.create_from_agent(payload)

        self.assertTrue(lead.id)
        self.assertEqual(lead.estimated_lbs_per_load, 0)

    def test_missing_raw_payload_defaults_gracefully(self):
        """Payload without raw_payload still creates valid record."""
        payload = self._build_payload(lead_id="WL-NORAW-001")
        del payload["raw_payload"]
        lead = self.WebLead.create_from_agent(payload)

        self.assertTrue(lead.id)
        self.assertEqual(lead.company_name, "Unknown")
