"""Unit tests for plasticos_crm_bridge CRM lead extension.

Tests cover:
- action_convert_to_intake creates intake + partner
- action_convert_to_intake uses existing partner when set
- action_convert_to_intake with no partner creates new one
- Computed counts: web_lead_count, intake_count
- Navigation actions return correct window actions
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCrmBridge(PlasticosTestCase):
    """Test CRM lead to intake conversion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "CRM Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.lead = cls.env["crm.lead"].create(
            {
                "name": "Test Scrap Lead",
                "partner_name": "Acme Recyclers CRM",
                "type": "lead",
            }
        )

    def test_convert_creates_intake(self):
        """action_convert_to_intake creates a plasticos.intake."""
        self.lead.partner_id = self.partner.id
        result = self.lead.action_convert_to_intake()
        self.assertEqual(result["res_model"], "plasticos.intake")
        intake = self.env["plasticos.intake"].browse(result["res_id"])
        self.assertEqual(intake.partner_id.id, self.partner.id)
        self.assertEqual(intake.crm_lead_id.id, self.lead.id)

    def test_convert_creates_partner_when_missing(self):
        """Conversion creates new partner from lead data when none set."""
        lead = self.env["crm.lead"].create(
            {
                "name": "New Partner Lead",
                "partner_name": "Brand New Recyclers",
                "type": "lead",
            }
        )
        result = lead.action_convert_to_intake()
        intake = self.env["plasticos.intake"].browse(result["res_id"])
        self.assertTrue(intake.partner_id)
        self.assertEqual(intake.partner_id.name, "Brand New Recyclers")
        self.assertTrue(intake.partner_id.is_company)

    def test_convert_uses_existing_partner(self):
        """Conversion uses existing partner when partner_id already set."""
        self.lead.partner_id = self.partner.id
        result = self.lead.action_convert_to_intake()
        intake = self.env["plasticos.intake"].browse(result["res_id"])
        self.assertEqual(intake.partner_id.id, self.partner.id)

    def test_intake_count_computed(self):
        """intake_count reflects linked intakes."""
        self.lead.partner_id = self.partner.id
        self.lead.action_convert_to_intake()
        self.lead.invalidate_recordset()
        self.assertGreaterEqual(self.lead.intake_count, 1)

    def test_navigation_actions(self):
        """Navigation actions return window actions."""
        self.lead.partner_id = self.partner.id
        self.lead.action_convert_to_intake()
        result = self.lead.action_view_intakes()
        self.assertEqual(result["res_model"], "plasticos.intake")
