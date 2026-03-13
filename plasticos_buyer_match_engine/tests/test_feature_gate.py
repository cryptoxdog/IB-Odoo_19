from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "feature_gate")
class TestFeatureGate(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.intake", "plasticos.feature.gate.mixin", "res.config.settings")
        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.Intake = cls.env["plasticos.intake"]
        cls.Gate = cls.env["plasticos.feature.gate.mixin"]

    def setUp(self):
        super().setUp()
        self.ICP.set_param("plasticos.matching_engine.enabled", "False")
        self.ICP.set_param("plasticos.inference_engine.enabled", "False")
        self.ICP.set_param(
            "plasticos.feature_gate.user_message",
            "This isn't ready - come back in 5 minutes!",
        )

    def _create_gated_intake(self):
        intake = self._create_intake(partner=self.default_partner, polymer=self.default_polymer, form=self.default_form)
        if intake is None:
            self.skipTest("plasticos.intake factory unavailable")
            return None  # Unreachable, but satisfies static analysis
        material_profile = self._create_material_profile(partner=self.default_partner, polymer=self.default_polymer)
        if material_profile is None:
            self.skipTest("plasticos.material.profile factory unavailable")
            return None  # Unreachable, but satisfies static analysis
        intake.write({"material_profile_id": material_profile.id})
        return intake

    def test_matching_action_blocked_when_disabled(self):
        intake = self._create_gated_intake()
        with self.assertRaises(UserError):
            intake.action_match_to_buyers()

    def test_matching_action_uses_custom_message_when_disabled(self):
        intake = self._create_gated_intake()
        custom_msg = "System upgrade in progress. Back in about an hour."
        self.ICP.set_param("plasticos.feature_gate.user_message", custom_msg)
        with self.assertRaises(UserError) as ctx:
            intake.action_match_to_buyers()
        self.assertIn(custom_msg, str(ctx.exception))

    def test_matching_gate_allows_method_path_when_enabled(self):
        intake = self._create_gated_intake()
        self.ICP.set_param("plasticos.matching_engine.enabled", "True")
        self.ICP.set_param("plasticos.matching_engine.stubbed", "False")
        with patch(
            "odoo.addons.plasticos_buyer_match_engine.models.intake_extension.PlasticosIntake._notify_neo4j_fallback"
        ) as notify:
            with patch.object(
                self.env["plasticos.buyer.matcher"],
                "find_matches_for_supplier",
                return_value=[],
            ) as matcher:
                result = intake.action_match_to_buyers()
        self.assertTrue(result)
        self.assertIn(result.get("type"), {"ir.actions.act_window", "ir.actions.client"})
        notify.assert_called()
        matcher.assert_called()

    def test_matching_action_survives_matcher_failure(self):
        intake = self._create_gated_intake()
        self.ICP.set_param("plasticos.matching_engine.enabled", "True")
        self.ICP.set_param("plasticos.matching_engine.stubbed", "False")
        with patch.object(
            self.env["plasticos.buyer.matcher"],
            "find_matches_for_supplier",
            side_effect=RuntimeError("matcher unavailable"),
        ):
            result = intake.action_match_to_buyers()
        self.assertIn(result.get("type"), {"ir.actions.act_window", "ir.actions.client"})

    def test_cron_skip_helper_returns_true_when_disabled(self):
        skipped = self.Gate._skip_feature_gate_for_cron(
            "plasticos.matching_engine.enabled", "intake_normalized_auto_match"
        )
        self.assertTrue(skipped)

    def test_cron_skip_helper_returns_false_when_enabled(self):
        self.ICP.set_param("plasticos.matching_engine.enabled", "True")
        skipped = self.Gate._skip_feature_gate_for_cron(
            "plasticos.matching_engine.enabled", "intake_normalized_auto_match"
        )
        self.assertFalse(skipped)

    def test_settings_fields_are_registered(self):
        settings = self.env["res.config.settings"]
        for field_name in [
            "plasticos_matching_engine_enabled",
            "plasticos_inference_engine_enabled",
            "plasticos_matching_engine_url",
            "plasticos_inference_engine_url",
            "plasticos_feature_gate_message",
        ]:
            self.assertIn(field_name, settings._fields)
