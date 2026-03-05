from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDocumentNative(TransactionCase):
    """Test suite for plasticos.document extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.document" not in cls.env:
            raise cls.skipTest("plasticos.document not installed")
        cls.Model = cls.env["plasticos.document"]

    def test_model_accessible(self):
        """Test plasticos.document model is accessible."""
        self.assertIn("plasticos.document", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
