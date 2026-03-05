from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntakeGraphHooks(TransactionCase):
    """Test suite for plasticos.intake extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.intake" not in cls.env:
            raise cls.skipTest("plasticos.intake not installed")
        cls.Model = cls.env["plasticos.intake"]

    def test_model_accessible(self):
        """Test plasticos.intake model is accessible."""
        self.assertIn("plasticos.intake", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
