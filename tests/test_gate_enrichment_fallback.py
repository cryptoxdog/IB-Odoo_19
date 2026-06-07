"""Odoo runtime tests for Gate-primary enrichment converge fallback (ROAD-GATE-013)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


def _fake_gate_result(packet_id="pkt-conv-1", correlation_id="corr-conv-1", final_fields=None):
    packet = SimpleNamespace(header=SimpleNamespace(packet_id=packet_id, correlation_id=correlation_id))
    payload = {"status": "ok", "final_fields": final_fields or {"website": "https://enriched.example"}}
    return {"packet": packet, "payload": payload}


@tagged("post_install", "-at_install", "plasticos", "enrichment", "gate")
class TestGateEnrichmentFallback(PlasticosTestCase):
    """Verify Gate converge -> local fallback ordering on plasticos.enrichment.run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.partner = cls._create_partner("Gate Converge Co", supplier_rank=1)

    def _new_run(self):
        return self.env["plasticos.enrichment.run"].create({"partner_id": self.partner.id})

    def test_gate_converge_stores_proposal_for_review(self):
        run = self._new_run()
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                "odoo.addons.plasticos_gate.services.gate_client.send_converge_action",
                return_value=_fake_gate_result(final_fields={"website": "https://enriched.example", "city": "Raleigh"}),
            ) as gate_call,
        ):
            run.action_execute()
        gate_call.assert_called_once()
        self.assertEqual(run.state, "review")
        self.assertEqual(run.engine_used, "gate")
        self.assertEqual(run.gate_packet_id, "pkt-conv-1")
        self.assertEqual(run.gate_correlation_id, "corr-conv-1")
        self.assertEqual(
            run.gate_proposal.get("proposed_partner_fields"),
            {"website": "https://enriched.example", "city": "Raleigh"},
        )

    def test_gate_disabled_uses_local_pipeline(self):
        run = self._new_run()
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=False),
            patch(
                "odoo.addons.plasticos_gate.services.gate_client.send_converge_action",
                side_effect=AssertionError("Gate must not be called when disabled"),
            ),
        ):
            # Local path requires sources; none added -> raises (proves local branch entered)
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertNotEqual(run.engine_used, "gate")

    def test_gate_failure_falls_back_to_local(self):
        run = self._new_run()
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                "odoo.addons.plasticos_gate.services.gate_client.send_converge_action",
                side_effect=RuntimeError("gate down"),
            ),
        ):
            # Gate raises -> caught -> local path -> no sources -> UserError
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertNotEqual(run.engine_used, "gate")
