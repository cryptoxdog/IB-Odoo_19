from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIrAttachment(PlasticosTestCase):
    """Test suite for ir.attachment extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "ir.attachment" not in cls.env:
            raise cls.skipTest("ir.attachment not installed")
        cls.Model = cls.env["ir.attachment"]

    def test_model_accessible(self):
        """Test ir.attachment model is accessible."""
        self.assertIn("ir.attachment", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
