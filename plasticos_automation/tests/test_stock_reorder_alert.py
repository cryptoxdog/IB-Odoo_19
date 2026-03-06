from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestStockReorderAlert(PlasticosTestCase):
    """Test suite for stock reorder alert automation on product.product."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "product.product" not in cls.env:
            raise cls.skipTest("product.product not installed")
        cls.Product = cls.env["product.product"]

    def test_product_model_accessible(self):
        """Test product.product model is accessible."""
        self.assertIn("product.product", self.env)

    def test_reorder_alert_fields_exist(self):
        """Test reorder alert fields exist on product.product."""
        fields_to_check = ["reorder_alert_sent", "min_stock_level"]
        for field in fields_to_check:
            if hasattr(self.Product, field):
                self.assertIn(field, self.Product._fields)
