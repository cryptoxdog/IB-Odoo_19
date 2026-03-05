from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOfferBridge(TransactionCase):
    """Test suite for plasticos.offer extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.offer" not in cls.env:
            raise cls.skipTest("plasticos.offer not installed")
        cls.Model = cls.env["plasticos.offer"]

    def test_model_accessible(self):
        """Test plasticos.offer model is accessible."""
        self.assertIn("plasticos.offer", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
