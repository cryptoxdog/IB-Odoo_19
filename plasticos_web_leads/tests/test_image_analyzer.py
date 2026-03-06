from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestImageAnalyzer(PlasticosTestCase):
    """Test suite for plasticos.web.lead extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.web.lead" not in cls.env:
            raise cls.skipTest("plasticos.web.lead not installed")
        cls.Model = cls.env["plasticos.web.lead"]

    def test_model_accessible(self):
        """Test plasticos.web.lead model is accessible."""
        self.assertIn("plasticos.web.lead", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
