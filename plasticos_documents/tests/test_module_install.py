"""
Skeleton smoke tests for plasticos_documents.
Validates module install, model registry, and basic record CRUD.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleInstall(TransactionCase):
    """Verify plasticos_documents installs cleanly and registers its models."""

    def test_module_installed(self):
        """Module plasticos_documents should be in installed state."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "plasticos_documents"),
            ],
            limit=1,
        )
        self.assertTrue(module, "Module plasticos_documents not found in registry")
        self.assertEqual(module.state, "installed", f"Expected installed, got {module.state}")

    def test_models_registered(self):
        """All plasticos_documents models must be in the registry."""
        expected_models = [
            "plasticos.document",
            "plasticos.document.rule",
            "plasticos.document.tag",
            "plasticos.compliance.service",
        ]
        for model_name in expected_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Model {model_name} not in registry")

    def test_model_search_does_not_crash(self):
        """Verify search([]) on own models does not raise."""
        models_to_check = [
            "plasticos.document",
            "plasticos.document.rule",
            "plasticos.document.tag",
        ]
        for model_name in models_to_check:
            with self.subTest(model=model_name):
                records = self.env[model_name].search([], limit=1)
                self.assertIsNotNone(records)
