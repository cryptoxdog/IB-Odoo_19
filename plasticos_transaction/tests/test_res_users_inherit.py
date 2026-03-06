from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestResUsersTransaction(PlasticosTestCase):
    """Test suite for res.users extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "res.users" not in cls.env:
            raise cls.skipTest("res.users not installed")
        cls.Model = cls.env["res.users"]

    def test_model_accessible(self):
        """Test res.users model is accessible."""
        self.assertIn("res.users", self.env)

    def test_model_fields_exist(self):
        """Test model has expected fields."""
        self.assertTrue(hasattr(self.Model, "_fields"))
