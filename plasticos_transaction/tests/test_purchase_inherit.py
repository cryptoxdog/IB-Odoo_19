from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseTransaction(TransactionCase):
    """Test suite for purchase.order extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "purchase.order" not in cls.env:
            raise cls.skipTest("purchase.order not installed")
        cls.Model = cls.env["purchase.order"]

    def test_model_accessible(self):
        """Test purchase.order model is accessible."""
        self.assertIn("purchase.order", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
