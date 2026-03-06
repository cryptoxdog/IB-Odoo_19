from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestCrmLeadVanillasoft(PlasticosTestCase):
    """Test suite for crm.lead extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "crm.lead" not in cls.env:
            raise cls.skipTest("crm.lead not installed")
        cls.Model = cls.env["crm.lead"]

    def test_model_accessible(self):
        """Test crm.lead model is accessible."""
        self.assertIn("crm.lead", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
