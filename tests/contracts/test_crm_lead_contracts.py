"""Contract tests for crm.lead PlastOS extensions.

crm.lead is inherited by:
  - plasticos_crm_bridge (crm_lead.py, crm_lead_vanillasoft.py)
  - plasticos_enrichment (via enrichment bridge — indirect)

These tests verify the fields and methods that the CRM→Intake
conversion flow depends on.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestCrmLeadContract(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Lead = cls.env["crm.lead"]
            cls.fields = cls.Lead._fields
            cls.skip_crm = False
        except KeyError:
            cls.skip_crm = True

    def _skip_if_no_crm(self):
        if self.skip_crm:
            self.skipTest("crm module not installed")

    def test_intake_ids_on_lead(self):
        self._skip_if_no_crm()
        self.assertIn("intake_ids", self.fields)

    def test_intake_count_on_lead(self):
        self._skip_if_no_crm()
        self.assertIn("intake_count", self.fields)

    def test_action_convert_to_intake_exists(self):
        """CRM bridge button calls this method."""
        self._skip_if_no_crm()
        self.assertTrue(
            callable(getattr(self.Lead, "action_convert_to_intake", None)),
            "action_convert_to_intake missing on crm.lead",
        )

    def test_material_profile_ids_on_lead(self):
        self._skip_if_no_crm()
        self.assertIn("material_profile_ids", self.fields)

    def test_web_opportunity_provenance_and_profile_fields(self):
        self._skip_if_no_crm()
        self.assertIn("source_intake_id", self.fields)
        self.assertIn("material_profile_id", self.fields)

    def test_partner_creation_is_compatible_with_optional_mobile_field(self):
        self._skip_if_no_crm()
        Partner = self.env["res.partner"]
        lead = self.Lead.create({"name": "Mobile compatibility contract", "type": "lead"})
        partner = lead._find_or_create_partner_from_lead()

        self.assertTrue(partner)
        if "mobile" in Partner._fields:
            self.assertEqual(partner.mobile, lead.mobile or False)
