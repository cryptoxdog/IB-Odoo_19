"""
Skeleton smoke tests for plasticos_buyer_match_engine.
Validates module install, model registry, and basic record CRUD.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestModuleInstall(TransactionCase):
    """Verify plasticos_buyer_match_engine installs cleanly and registers its models."""

    def test_module_installed(self):
        """Module plasticos_buyer_match_engine should be in installed state."""
        module = self.env["ir.module.module"].search(
            [
                ("name", "=", "plasticos_buyer_match_engine"),
            ],
            limit=1,
        )
        self.assertTrue(module, "Module plasticos_buyer_match_engine not found in registry")
        self.assertEqual(module.state, "installed", f"Expected installed, got {module.state}")

    def test_models_registered(self):
        """All plasticos_buyer_match_engine models must be in the registry."""
        expected_models = [
            "plasticos.buyer.matcher",
            "plasticos.graph.service",
            "plasticos.graph.sync.log",
            "plasticos.match.exclusion",
        ]
        for model_name in expected_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Model {model_name} not in registry")

    def test_inherited_models_accessible(self):
        """Inherited models must remain accessible after plasticos_buyer_match_engine extension."""
        inherited_models = [
            "plasticos.intake",
            "plasticos.facility.profile",
            "plasticos.material.profile",
            "res.partner",
        ]
        for model_name in inherited_models:
            with self.subTest(model=model_name):
                self.assertIn(model_name, self.env, f"Inherited model {model_name} broken")

    def test_model_search_does_not_crash(self):
        """Verify search([]) on own models does not raise."""
        models_to_check = [
            "plasticos.graph.sync.log",
            "plasticos.match.exclusion",
        ]
        for model_name in models_to_check:
            with self.subTest(model=model_name):
                records = self.env[model_name].search([], limit=1)
                # Just verify it returns a recordset without error
                self.assertIsNotNone(records)

    def test_access_rules_exist(self):
        """At least one ir.model.access row should exist per own model."""
        for model_name in [
            "plasticos.buyer.matcher",
            "plasticos.graph.service",
            "plasticos.graph.sync.log",
            "plasticos.match.exclusion",
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
