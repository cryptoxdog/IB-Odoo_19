"""Contract tests for crm.lead PlastOS extensions.

crm.lead is inherited by:
  - plasticos_crm_bridge (crm_lead.py, crm_lead_vanillasoft.py)
  - plasticos_enrichment (via enrichment bridge — indirect)

These tests verify the fields and methods that the CRM→Intake
conversion flow depends on.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "contract")
class TestCrmLeadContract(TransactionCase):
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
