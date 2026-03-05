from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAccountMoveTransaction(TransactionCase):
    """Test suite for account.move extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "account.move" not in cls.env:
            raise cls.skipTest("account.move not installed")
        cls.Model = cls.env["account.move"]

    def test_model_accessible(self):
        """Test account.move model is accessible."""
        self.assertIn("account.move", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
