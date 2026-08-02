"""Odoo runtime tests for Gate-primary matcher fallback ordering."""

from __future__ import annotations

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "matching", "gate")
class TestGateMatcherFallback(PlasticosTestCase):
    """Verify stub → gate → local call order on plasticos.buyer.matcher."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.buyer.matcher")
        cls.matcher = cls.env["plasticos.buyer.matcher"]
        cls.supplier = cls._create_partner("Gate Fallback Supplier", supplier_rank=1)

    def test_stub_runs_before_gate_and_returns_empty(self):
        local_payload = [{"buyer_id": 1, "total_score": 0.5, "gates_passed": 1, "gates_failed": []}]
        with (
            patch.object(type(self.matcher), "_matching_stub_enabled", return_value=True),
            patch(
                "odoo.addons.plasticos_gate.services.gate_client.send_match_action",
                side_effect=AssertionError("Gate must not run when stub enabled"),
            ) as gate_call,
            patch.object(type(self.matcher), "_find_matches_local", return_value=local_payload) as local_call,
        ):
            result = self.matcher.find_matches_for_supplier(self.supplier.id)
        self.assertEqual(result, [])
        gate_call.assert_not_called()
        local_call.assert_not_called()

    def test_gate_disabled_uses_local_only(self):
        local_payload = [
            {
                "buyer_id": self.supplier.id,
                "buyer_name": self.supplier.name,
                "total_score": 0.4,
                "gates_passed": 2,
                "gates_failed": [],
                "match_details": {},
                "facility_profile_id": False,
                "typical_price": 0.0,
            }
        ]
        with (
            patch.object(type(self.matcher), "_matching_stub_enabled", return_value=False),
            patch(
                "odoo.addons.plasticos_gate.services.gate_config.gate_matching_enabled",
                return_value=False,
            ),
            patch(
                "odoo.addons.plasticos_gate.services.gate_client.send_match_action",
                side_effect=AssertionError("Gate must not run when disabled"),
            ) as gate_call,
            patch.object(type(self.matcher), "_find_matches_local", return_value=local_payload) as local_call,
        ):
            result = self.matcher.find_matches_for_supplier(self.supplier.id)
        self.assertEqual(result, local_payload)
        gate_call.assert_not_called()
        local_call.assert_called_once()

    def test_gate_failure_falls_back_to_local(self):
        local_payload = [
            {
                "buyer_id": self.supplier.id,
                "buyer_name": self.supplier.name,
                "total_score": 0.6,
                "gates_passed": 3,
                "gates_failed": [],
                "match_details": {},
                "facility_profile_id": False,
                "typical_price": 0.0,
            }
        ]
        with (
            patch.object(type(self.matcher), "_matching_stub_enabled", return_value=False),
            patch(
                "odoo.addons.plasticos_gate.services.gate_config.gate_matching_enabled",
                return_value=True,
            ),
            patch(
                "odoo.addons.plasticos_gate.services.gate_client.send_match_action",
                side_effect=RuntimeError("gate down"),
            ),
            patch.object(type(self.matcher), "_find_matches_local", return_value=local_payload) as local_call,
        ):
            result = self.matcher.find_matches_for_supplier(self.supplier.id)
        self.assertEqual(result, local_payload)
        local_call.assert_called_once()
