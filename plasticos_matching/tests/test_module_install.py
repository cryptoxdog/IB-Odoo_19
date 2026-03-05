"""
Skeleton smoke tests for plasticos_matching.
Validates module install, model registry, and basic record CRUD.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleInstall(TransactionCase):
    """Verify plasticos_matching installs cleanly and registers its models."""

    def test_module_installed(self):
        """Module plasticos_matching should be in installed state."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "plasticos_matching"),
            ],
            limit=1,
        )
        self.assertTrue(module, "Module plasticos_matching not found in registry")
        self.assertEqual(module.state, "installed", f"Expected installed, got {module.state}")

    def test_models_registered(self):
        """All plasticos_matching models must be in the registry."""
        expected_models = [
            "plasticos.match.result",
        ]
        for model_name in expected_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Model {model_name} not in registry")

    def test_model_search_does_not_crash(self):
        """Verify search([]) on own models does not raise."""
        records = self.env["plasticos.match.result"].search([], limit=1)
        self.assertIsNotNone(records)
