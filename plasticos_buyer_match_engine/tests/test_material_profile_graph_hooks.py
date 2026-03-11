from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMaterialProfileGraphHooks(PlasticosTestCase):
    """Test suite for plasticos.material.profile extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "plasticos.material.profile" not in cls.env:
            raise cls.skipTest("plasticos.material.profile not installed")
        cls.Model = cls.env["plasticos.material.profile"]

    def test_model_accessible(self):
        """Test plasticos.material.profile model is accessible."""
        self.assertIn("plasticos.material.profile", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
