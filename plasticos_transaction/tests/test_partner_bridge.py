from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPartnerBridge(PlasticosTestCase):
    """Test suite for res.partner extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "res.partner" not in cls.env:
            raise cls.skipTest("res.partner not installed")
        cls.Model = cls.env["res.partner"]

    def test_model_accessible(self):
        """Test res.partner model is accessible."""
        self.assertIn("res.partner", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
