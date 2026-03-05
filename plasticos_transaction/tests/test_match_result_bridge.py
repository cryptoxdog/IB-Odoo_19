from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMatchResultBridge(TransactionCase):
    """Test suite for plasticos.match.result extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.match.result" not in cls.env:
            raise cls.skipTest("plasticos.match.result not installed")
        cls.Model = cls.env["plasticos.match.result"]

    def test_model_accessible(self):
        """Test plasticos.match.result model is accessible."""
        self.assertIn("plasticos.match.result", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
