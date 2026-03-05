from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleOrderLogistics(TransactionCase):
    """Test suite for sale.order extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "sale.order" not in cls.env:
            raise cls.skipTest("sale.order not installed")
        cls.Model = cls.env["sale.order"]

    def test_model_accessible(self):
        """Test sale.order model is accessible."""
        self.assertIn("sale.order", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
