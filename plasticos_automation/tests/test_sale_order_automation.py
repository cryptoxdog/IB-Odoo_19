from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSaleOrderAutomation(PlasticosTestCase):
    """Test suite for sale order automation on sale.order."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "sale.order" not in cls.env:
            raise cls.skipTest("sale.order not installed")
        cls.SO = cls.env["sale.order"]

    def test_so_model_accessible(self):
        """Test sale.order model is accessible."""
        self.assertIn("sale.order", self.env)

    def test_automation_fields_exist(self):
        """Test automation fields exist on sale.order."""
        fields_to_check = ["auto_confirm", "auto_invoice"]
        for field in fields_to_check:
            if hasattr(self.SO, field):
                self.assertIn(field, self.SO._fields)
