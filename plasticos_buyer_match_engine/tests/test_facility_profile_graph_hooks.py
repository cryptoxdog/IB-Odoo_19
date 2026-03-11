from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFacilityProfileGraphHooks(PlasticosTestCase):
    """Test suite for plasticos.facility.profile extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.facility.profile" not in cls.env:
            raise cls.skipTest("plasticos.facility.profile not installed")
        cls.Model = cls.env["plasticos.facility.profile"]

    def test_model_accessible(self):
        """Test plasticos.facility.profile model is accessible."""
        self.assertIn("plasticos.facility.profile", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
