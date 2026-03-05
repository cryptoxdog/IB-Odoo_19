from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTransactionLogistics(TransactionCase):
    """Test suite for plasticos.transaction extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.transaction" not in cls.env:
            raise cls.skipTest("plasticos.transaction not installed")
        cls.Model = cls.env["plasticos.transaction"]

    def test_model_accessible(self):
        """Test plasticos.transaction model is accessible."""
        self.assertIn("plasticos.transaction", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
