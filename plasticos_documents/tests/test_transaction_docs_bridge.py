from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestTransactionDocsBridge(PlasticosTestCase):
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
