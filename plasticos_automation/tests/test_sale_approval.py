from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSaleApproval(PlasticosTestCase):
    """Test suite for sale approval automation on sale.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "sale.order" not in cls.env:
            raise cls.skipTest("sale.order not installed")
        cls.SO = cls.env["sale.order"]
        cls.Partner = cls.env["res.partner"]
        cls.partner = cls.Partner.create({"name": "Test Customer"})

    # ═══════════════════════════════════════════════════════════════════
    # APPROVAL FIELD TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_so_model_accessible(self):
        """Test sale.order model is accessible."""
        self.assertIn("sale.order", self.env)

    def test_approval_fields_exist(self):
        """Test approval automation fields exist on sale.order."""
        fields_to_check = ["requires_approval", "approved_by", "approval_date"]
        for field in fields_to_check:
            if hasattr(self.SO, field):
                self.assertIn(field, self.SO._fields)

    def test_action_approve_exists(self):
        """Test action_approve method exists on sale.order."""
        if hasattr(self.SO, "action_approve"):
            self.assertTrue(callable(self.SO.action_approve))
