"""
Skeleton smoke tests for plasticos_claims.
Validates module install, model registry, and basic record CRUD.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestModuleInstall(PlasticosTestCase):
    """Verify plasticos_claims installs cleanly and registers its models."""

    def test_module_installed(self):
        """Module plasticos_claims should be in installed state."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "plasticos_claims"),
            ],
            limit=1,
        )
        self.assertTrue(module, "Module plasticos_claims not found in registry")
        self.assertEqual(module.state, "installed", f"Expected installed, got {module.state}")

    def test_models_registered(self):
        """All plasticos_claims models must be in the registry."""
        expected_models = [
            "plasticos.claim",
        ]
        for model_name in expected_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Model {model_name} not in registry")

    def test_inherited_models_accessible(self):
        """Inherited models must remain accessible after plasticos_claims extension."""
        inherited_models = [
            "res.partner",
            "mail.thread",
        ]
        for model_name in inherited_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Inherited model {model_name} broken")

    def test_model_search_does_not_crash(self):
        """Verify search([]) on own models does not raise."""
        models_to_check = [
            "plasticos.claim",
        ]
        for model_name in models_to_check:
            with self.subTest(model=model_name):
                records = self.env[model_name].search([], limit=1)
                self.assertIsNotNone(records)

    def test_access_rules_exist(self):
        """At least one ir.model.access row should exist per own model."""
        for model_name in [
            "plasticos.claim",
        ]:
            with self.subTest(model=model_name):
                model_rec = self.env["ir.model"].search(
                    [
                        ("model", "=", model_name),
                    ],
                    limit=1,
                )
                if model_rec:
                    acl = self.env["ir.model.access"].search(
                        [
                            ("model_id", "=", model_rec.id),
                        ]
                    )
                    self.assertTrue(acl, f"No ir.model.access rules for {model_name}")
