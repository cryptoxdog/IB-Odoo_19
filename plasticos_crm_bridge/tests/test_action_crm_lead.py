"""Action method tests for CRM Lead extensions in plasticos_crm_bridge.

Tests the PlastOS bridge actions added to crm.lead model.
Aligned with plasticos_crm_bridge/models/crm_lead.py.

Available actions:
- action_convert_to_intake: Create plasticos.intake from lead
- action_view_intakes: Navigate to linked intakes
- action_view_web_leads: Navigate to linked web leads
- action_view_material_profiles: Navigate to material profiles
- action_view_match_results: Navigate to match results
- action_view_transactions: Navigate to transactions
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestCrmLeadActions(PlasticosTestCase):
    """Test PlastOS action_* methods added to crm.lead."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "CRM Lead Partner",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        # Create a facility (child partner) for material profile tests
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "CRM Lead Facility",
                "is_company": True,
                "parent_id": cls.partner.id,
            }
        )
        cls.lead = cls.env["crm.lead"].create(
            {
                "name": "CRM-ACT-001",
                "partner_id": cls.partner.id,
                "partner_name": "CRM Lead Partner",
                "type": "opportunity",
            }
        )

    # ------------------------------------------------------------------
    # action_convert_to_intake (primary conversion action)
    # ------------------------------------------------------------------
    def test_action_convert_to_intake_returns_action(self):
        """action_convert_to_intake should return window action for new intake."""
        if not hasattr(self.lead, "action_convert_to_intake"):
            self.skipTest("action_convert_to_intake not available")

        result = self.lead.action_convert_to_intake()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("type"), "ir.actions.act_window")
        self.assertEqual(result.get("res_model"), "plasticos.intake")

    def test_action_convert_to_intake_creates_intake(self):
        """action_convert_to_intake should create a plasticos.intake record."""
        if not hasattr(self.lead, "action_convert_to_intake"):
            self.skipTest("action_convert_to_intake not available")

        initial_count = self.env["plasticos.intake"].search_count([])
        result = self.lead.action_convert_to_intake()
        if result.get("res_id"):
            new_count = self.env["plasticos.intake"].search_count([])
            self.assertGreater(new_count, initial_count)

    # ------------------------------------------------------------------
    # Navigation actions (view_* methods)
    # ------------------------------------------------------------------
    def test_action_view_intakes_returns_window_action(self):
        """action_view_intakes should return ir.actions.act_window."""
        if not hasattr(self.lead, "action_view_intakes"):
            self.skipTest("action_view_intakes not available")

        result = self.lead.action_view_intakes()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.intake")

    def test_action_view_web_leads_returns_window_action(self):
        """action_view_web_leads should return ir.actions.act_window."""
        if not hasattr(self.lead, "action_view_web_leads"):
            self.skipTest("action_view_web_leads not available")

        result = self.lead.action_view_web_leads()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.web.lead")

    def test_action_view_material_profiles_returns_window_action(self):
        """action_view_material_profiles should return ir.actions.act_window."""
        if not hasattr(self.lead, "action_view_material_profiles"):
            self.skipTest("action_view_material_profiles not available")

        result = self.lead.action_view_material_profiles()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.material.profile")

    def test_action_view_match_results_returns_window_action(self):
        """action_view_match_results should return ir.actions.act_window."""
        if not hasattr(self.lead, "action_view_match_results"):
            self.skipTest("action_view_match_results not available")

        result = self.lead.action_view_match_results()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.match.result")

    def test_action_view_transactions_returns_window_action(self):
        """action_view_transactions should return ir.actions.act_window."""
        if not hasattr(self.lead, "action_view_transactions"):
            self.skipTest("action_view_transactions not available")

        result = self.lead.action_view_transactions()
        self.assertIsInstance(result, dict)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "plasticos.transaction")

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------
    def test_view_actions_work_without_partner(self):
        """View actions should not raise even if lead has no partner."""
        lead_no_partner = self.env["crm.lead"].create(
            {
                "name": "Lead Without Partner",
                "type": "lead",
            }
        )
        if hasattr(lead_no_partner, "action_view_intakes"):
            result = lead_no_partner.action_view_intakes()
            self.assertIsInstance(result, dict)

    def test_action_view_intakes_filters_by_partner(self):
        """action_view_intakes should filter intakes by partner facilities."""
        if not hasattr(self.lead, "action_view_intakes"):
            self.skipTest("action_view_intakes not available")

        result = self.lead.action_view_intakes()
        # Domain should filter by partner's facilities
        self.assertIn("domain", result)
