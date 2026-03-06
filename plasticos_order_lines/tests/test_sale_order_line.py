from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestSaleOrderLine(PlasticosTestCase):
    """Test suite for sale.order.line extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "sale.order.line" not in cls.env:
            raise cls.skipTest("sale.order.line not installed")
        cls.Model = cls.env["sale.order.line"]

    def test_model_accessible(self):
        """Test sale.order.line model is accessible."""
        self.assertIn("sale.order.line", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
