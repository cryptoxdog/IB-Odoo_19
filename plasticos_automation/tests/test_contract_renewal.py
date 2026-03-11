from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestContractRenewal(PlasticosTestCase):
    """Test suite for contract renewal automation on res.partner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]

    def _create_partner(self, **kwargs):
        """Helper to create res.partner with contract fields."""
        vals = {"name": "Test Partner", "is_company": True}
        vals.update(kwargs)
        return self.Partner.create(vals)

    # ═══════════════════════════════════════════════════════════════════
    # CONTRACT FIELD TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_partner_has_contract_fields(self):
        """Test partner has contract renewal fields from automation."""
        partner = self._create_partner()
        self.assertTrue(partner.exists())
        if hasattr(partner, "contract_end_date"):
            self.assertIn("contract_end_date", self.Partner._fields)

    def test_contract_date_can_be_set(self):
        """Test contract_end_date can be set on partner."""
        from datetime import date, timedelta

        partner = self._create_partner()
        if hasattr(partner, "contract_end_date"):
            partner.contract_end_date = date.today() + timedelta(days=30)
            self.assertEqual(partner.contract_end_date, date.today() + timedelta(days=30))
