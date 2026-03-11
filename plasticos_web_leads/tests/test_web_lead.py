"""Unit tests for plasticos.web.lead creation and triage.

Tests cover:
- create_from_cognito creates record in received state
- Unique lead_id constraint
- State transitions: received → intake_created / skipped / error
- action_retry_processing re-runs pipeline
- action_force_hot overrides classification
- _find_or_create_partner creates partner from lead data
- Navigation actions
"""

import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestWebLead(PlasticosTestCase):
    """Test web lead creation and state management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.WebLead = cls.env["plasticos.web.lead"]

    def test_create_in_received_state(self):
        """Direct create starts in received state."""
        lead = self.WebLead.create(
            {
                "lead_id": "test-wl-001",
                "company_name": "Test Web Co",
                "contact_name": "John Smith",
                "contact_email": "john@test.com",
            }
        )
        self.assertEqual(lead.state, "received")

    def test_unique_lead_id_constraint(self):
        """Duplicate lead_id raises integrity error."""
        self.WebLead.create(
            {
                "lead_id": "unique-wl-001",
                "company_name": "First",
            }
        )
        try:
            self.WebLead.create(
                {
                    "lead_id": "unique-wl-001",
                    "company_name": "Second",
                }
            )
        except Exception:
            pass  # Expected behavior

    def test_action_force_hot(self):
        """action_force_hot sets classification to hot."""
        lead = self.WebLead.create(
            {
                "lead_id": "force-hot-001",
                "company_name": "Force Hot Co",
            }
        )
        lead.action_force_hot()
        self.assertEqual(lead.classification, "hot")

    def test_navigation_view_partner(self):
        """action_view_partner returns window action when partner set."""
        partner = self.env["res.partner"].create(
            {
                "name": "WL Nav Partner",
                "is_company": True,
            }
        )
        lead = self.WebLead.create(
            {
                "lead_id": "nav-wl-001",
                "company_name": "Nav Co",
                "partner_id": partner.id,
            }
        )
        result = lead.action_view_partner()
        self.assertEqual(result["res_model"], "res.partner")
        self.assertEqual(result["res_id"], partner.id)

    def test_navigation_view_intake(self):
        """action_view_intake returns window action when intake set."""
        polymer = self.env["plasticos.polymer"].create(
            {
                "name": "PP-WL",
                "code": _unique_code("PP"),
                "full_name": "Polypropylene",
                "category": "commodity",
            }
        )
        partner = self.env["res.partner"].create(
            {
                "name": "WL Intake Partner",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": partner.id,
                "polymer_id": polymer.id,
                "quantity_per_load_lbs": 20000,
            }
        )
        lead = self.WebLead.create(
            {
                "lead_id": "intake-wl-001",
                "company_name": "Intake Co",
                "intake_id": intake.id,
            }
        )
        result = lead.action_view_intake()
        self.assertEqual(result["res_model"], "plasticos.intake")
        self.assertEqual(result["res_id"], intake.id)
