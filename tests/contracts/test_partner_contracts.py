"""Contract tests for res.partner PlastOS extensions.

res.partner is inherited by 8+ PlastOS modules:
  - plasticos_facility_profile (facility_profile_ids, partner_type_id)
  - plasticos_security_base (entity_status, etc.)
  - plasticos_geolocalize (lat, lon, geo_status)
  - plasticos_material_profile (material_profile_ids)
  - plasticos_enrichment (enrichment_source_ids)
  - plasticos_automation (contract_end_date, contract_alert_sent)
  - plasticos_intake (res_partner_intake.py)
  - plasticos_transaction (partner_bridge.py)
  - plasticos_buyer_match_engine (facility_profile_graph_hooks.py)
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
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
        f = self.fields.get("intake_ids")
        self.assertIsNotNone(f, "intake_ids missing — partner form smart button needs it")

    def test_intake_count_exists(self):
        self.assertIn("intake_count", self.fields)

    # ── From plasticos_automation ──
    def test_contract_fields_exist(self):
        """Contract renewal cron depends on these."""
        for fname in ("contract_end_date", "contract_alert_sent"):
            self.assertIn(fname, self.fields, f"Missing automation field: {fname}")

    # ── From plasticos_enrichment ──
    def test_enrichment_source_ids_exists(self):
        self.assertIn("enrichment_source_ids", self.fields)

    # ── Preferred contact memory (intake onchange depends on this) ──
    def test_preferred_contact_id_exists(self):
        """Intake auto-selects contact via x_preferred_contact_id."""
        self.assertIn("x_preferred_contact_id", self.fields)

    # ── Lead source (intake sync) ──
    def test_lead_source_id_exists(self):
        self.assertIn("lead_source_id", self.fields)
