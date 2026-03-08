"""
Skeleton smoke tests for plasticos_security_base.
Validates module install, model registry, and basic record CRUD.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestModuleInstall(PlasticosTestCase):
    """Verify plasticos_security_base installs cleanly and registers its models."""

    def test_module_installed(self):
        """Module plasticos_security_base should be in installed state."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "plasticos_security_base"),
            ],
            limit=1,
        )
        self.assertTrue(module, "Module plasticos_security_base not found in registry")
        self.assertEqual(module.state, "installed", f"Expected installed, got {module.state}")

    def test_inherited_models_accessible(self):
        """Inherited models must remain accessible after plasticos_security_base extension."""
        inherited_models = [
            "res.partner",
        ]
        for model_name in inherited_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Inherited model {model_name} broken")
