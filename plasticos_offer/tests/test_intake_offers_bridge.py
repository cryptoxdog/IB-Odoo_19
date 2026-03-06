from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIntakeOffersBridge(PlasticosTestCase):
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
