"""Contract tests for res.partner PlastOS extensions.

res.partner is inherited by 8+ PlastOS modules:
  - plasticos_facility_profile (facility_profile_ids, partner_type_id)
  - plasticos_security_base (entity_status, etc.)
  - plasticos_geolocalize (lat, lon, geo_status)
  - plasticos_material_profile (material_profile_ids)
  - plasticos_enrichment (enrichment_source_ids)
  - plasticos_automation (contract_end_date, cron_contract_renewal_alert)
  - plasticos_intake (res_partner_intake.py: intake_count, action_view_intakes)
  - plasticos_transaction (partner_bridge.py)
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "contract")
class TestPartnerFieldContract(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.fields = cls.Partner._fields

    # ── From plasticos_security_base ──
    def test_entity_status_exists(self):
        """Intake reads this via related field partner_entity_status."""
        self.assertIn("entity_status", self.fields)

    # ── From plasticos_facility_profile ──
    def test_facility_profile_ids_exists(self):
        """Buyer match engine traverses facility profiles."""
        f = self.fields.get("facility_profile_ids")
        self.assertIsNotNone(f, "facility_profile_ids missing — match engine needs it")

    def test_partner_type_id_exists(self):
        self.assertIn("partner_type_id", self.fields)

    # ── From plasticos_material_profile ──
    def test_material_profile_ids_exists(self):
        f = self.fields.get("material_profile_ids")
        self.assertIsNotNone(f, "material_profile_ids missing — CRM bridge needs it")

    # ── From plasticos_geolocalize ──
    def test_geo_fields_on_partner(self):
        """Freight automation and geo backfill depend on these."""
        for fname in ("partner_latitude", "partner_longitude"):
            # Odoo base uses partner_latitude/partner_longitude
            # plasticos_geolocalize may add lat/lon aliases
            has_field = fname in self.fields or fname.replace("partner_", "") in self.fields
            self.assertTrue(has_field, f"Missing geo field: {fname}")

    # ── From plasticos_intake (res_partner_intake.py) ──
    def test_intake_ids_exists(self):
        """The partner form smart button is backed by intake_count + action_view_intakes, which
        select intakes by company OR facility (plasticos_intake/models/res_partner_intake.py:17-47,
        views/material_profile_intake_views.xml:59-64); res.partner declares no intake_ids relation."""
        partner = self.Partner.create({"name": "Intake Navigation Partner", "is_company": True})
        action = partner.action_view_intakes()
        self.assertEqual(action["res_model"], "plasticos.intake")
        self.assertEqual(action["domain"], ["|", ("partner_id", "=", partner.id), ("facility_id", "=", partner.id)])
        intake = self._create_intake(partner=partner)
        self.assertEqual(self.env["plasticos.intake"].search(action["domain"]), intake)
        partner.invalidate_recordset(["intake_count"])
        self.assertEqual(partner.intake_count, 1)

    def test_intake_count_exists(self):
        self.assertIn("intake_count", self.fields)

    # ── From plasticos_automation ──
    def test_contract_fields_exist(self):
        """Contract renewal cron depends on these.

        The cron selects partners by contract_end_date and de-duplicates alerts through a same-day
        plasticos.automation.log row of action_type "contract_alert", not a partner flag
        (plasticos_automation/models/contract_renewal.py:12,29-64; models/automation_log.py:28).
        """
        self.assertIn("contract_end_date", self.fields)
        self.assertEqual(self.fields["contract_end_date"].type, "date")
        self.assertTrue(callable(getattr(self.Partner, "cron_contract_renewal_alert", None)))
        action_types = self.env["plasticos.automation.log"]._fields["action_type"].get_values(self.env)
        self.assertIn("contract_alert", action_types)

    # ── From plasticos_enrichment ──
    def test_enrichment_source_ids_exists(self):
        self.assertIn("enrichment_source_ids", self.fields)

    # ── Preferred contact memory (intake onchange depends on this) ──
    def test_preferred_contact_id_exists(self):
        """Intake auto-selects contact via preferred_contact_id."""
        self.assertIn("preferred_contact_id", self.fields)

    # ── Lead source (intake sync) ──
    def test_lead_source_id_exists(self):
        self.assertIn("lead_source_id", self.fields)
