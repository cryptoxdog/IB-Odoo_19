from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductTemplate(TransactionCase):
    """Test suite for product.template extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "product.template" not in cls.env:
            raise cls.skipTest("product.template not installed")
        cls.Model = cls.env["product.template"]

    def test_model_accessible(self):
        """Test product.template model is accessible."""
        self.assertIn("product.template", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
