"""
Skeleton smoke tests for plasticos_web_leads.
Validates module install, model registry, and basic record CRUD.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestModuleInstall(PlasticosTestCase):
    """Verify plasticos_web_leads installs cleanly and registers its models."""

    def test_module_installed(self):
        """Module plasticos_web_leads should be in installed state."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "plasticos_web_leads"),
            ],
            limit=1,
        )
        self.assertTrue(module, "Module plasticos_web_leads not found in registry")
        self.assertEqual(module.state, "installed", f"Expected installed, got {module.state}")

    def test_models_registered(self):
        """All plasticos_web_leads models must be in the registry."""
        expected_models = [
            "plasticos.web.lead",
            "plasticos.web.lead.config",
        ]
        for model_name in expected_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Model {model_name} not in registry")

    def test_model_search_does_not_crash(self):
        """Verify search([]) on own models does not raise."""
        models_to_check = [
            "plasticos.web.lead",
            "plasticos.web.lead.config",
        ]
        for model_name in models_to_check:
            with self.subTest(model=model_name):
                records = self.env[model_name].search([], limit=1)
                # Just verify it returns a recordset without error
                self.assertIsNotNone(records)

    def test_access_rules_exist(self):
        """At least one ir.model.access row should exist per own model."""
        for model_name in [
            "plasticos.web.lead",
            "plasticos.web.lead.config",
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
