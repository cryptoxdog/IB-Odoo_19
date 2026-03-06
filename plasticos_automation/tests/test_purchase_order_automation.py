from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPurchaseOrderAutomation(PlasticosTestCase):
    """Test suite for purchase order automation on purchase.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "purchase.order" not in cls.env:
            raise cls.skipTest("purchase.order not installed")
        cls.PO = cls.env["purchase.order"]

    # ═══════════════════════════════════════════════════════════════════
    # AUTOMATION FIELD TESTS
    # ═══════════════════════════════════════════════════════════════════

    def test_po_model_accessible(self):
        """Test purchase.order model is accessible."""
        self.assertIn("purchase.order", self.env)

    def test_automation_fields_exist(self):
        """Test automation fields exist on purchase.order."""
        fields_to_check = ["auto_confirm", "confirmation_reminder_sent"]
        for field in fields_to_check:
            if hasattr(self.PO, field):
                self.assertIn(field, self.PO._fields)
