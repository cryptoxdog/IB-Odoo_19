from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPurchaseOrderLine(PlasticosTestCase):
    """Test suite for purchase.order.line extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "purchase.order.line" not in cls.env:
            raise cls.skipTest("purchase.order.line not installed")
        cls.Model = cls.env["purchase.order.line"]

    def test_model_accessible(self):
        """Test purchase.order.line model is accessible."""
        self.assertIn("purchase.order.line", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
