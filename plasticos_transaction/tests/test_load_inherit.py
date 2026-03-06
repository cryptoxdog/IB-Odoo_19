from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestLoadTransaction(PlasticosTestCase):
    """Test suite for plasticos.load extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.load" not in cls.env:
            raise cls.skipTest("plasticos.load not installed")
        cls.Model = cls.env["plasticos.load"]

    def test_model_accessible(self):
        """Test plasticos.load model is accessible."""
        self.assertIn("plasticos.load", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
