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
        """crm.lead carries no material_profile_ids relation: its materials are resolved through
        the facility profile, a facility partner, or the partner's child facilities
        (plasticos_crm_bridge/models/crm_lead.py:191-200), counted by material_profile_count
        (crm_lead.py:83) and opened by action_view_material_profiles (crm_lead.py:456)."""
        self._skip_if_no_crm()
        self.assertIn("material_profile_count", self.fields)
        self.assertTrue(callable(getattr(self.Lead, "_linked_material_profiles", None)))
        facility = self.env["res.partner"].create({"name": "Lead Material Facility", "is_company": True})
        company = self.env["res.partner"].create(
            {"name": "Lead Material Company", "is_company": True, "child_ids": [(4, facility.id)]}
        )
        profile = self._create_material_profile(partner=facility)
        lead = self.Lead.create({"name": "Material profile contract", "type": "lead", "partner_id": company.id})
        self.assertIn(profile, lead._linked_material_profiles())
        self.assertEqual(lead.material_profile_count, len(lead._linked_material_profiles()))
        action = lead.action_view_material_profiles()
        self.assertEqual(action["res_model"], "plasticos.material.profile")
        self.assertEqual(self.env["plasticos.material.profile"].search(action["domain"]), profile)

    def test_web_opportunity_provenance_and_profile_fields(self):
        self._skip_if_no_crm()
        self.assertIn("source_intake_id", self.fields)
        self.assertIn("material_profile_id", self.fields)
        self.assertIn("commercial_image_count", self.fields)
        self.assertTrue(callable(getattr(self.Lead, "action_sync_commercial_images", None)))

    def test_partner_creation_is_compatible_with_optional_mobile_field(self):
        self._skip_if_no_crm()
        Partner = self.env["res.partner"]
        lead = self.Lead.create({"name": "Mobile compatibility contract", "type": "lead"})
        partner = lead._find_or_create_partner_from_lead()

        self.assertTrue(partner)
        if "mobile" in Partner._fields:
            self.assertEqual(partner.mobile, lead.mobile or False)
