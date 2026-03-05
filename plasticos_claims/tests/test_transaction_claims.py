from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTransactionClaims(TransactionCase):
    """Test suite for plasticos.claim extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.claim" not in cls.env:
            raise cls.skipTest("plasticos.claim not installed")
        cls.Model = cls.env["plasticos.claim"]

    def test_model_accessible(self):
        """Test plasticos.claim model is accessible."""
        self.assertIn("plasticos.claim", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
