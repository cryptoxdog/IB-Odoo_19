"""Odoo runtime tests for Gate-only enrichment converge (mothball M4).

Live auto-writeback, merge-not-overwrite, review-only opt-out, and
fail-closed degraded mode (no local crawl/inference substitute).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

_SEND = "odoo.addons.plasticos_gate.services.gate_client.send_converge_action"


def _fake_gate_result(packet_id="pkt-conv-1", correlation_id="corr-conv-1", final_fields=None):
    packet = SimpleNamespace(header=SimpleNamespace(packet_id=packet_id, correlation_id=correlation_id))
    payload = {"status": "ok", "final_fields": final_fields or {"website": "https://enriched.example"}}
    return {"packet": packet, "payload": payload}


@tagged("post_install", "-at_install", "plasticos", "enrichment", "gate")
class TestGateEnrichmentFallback(PlasticosTestCase):
    """Verify Gate converge writeback + M4 no-local-substitute degraded mode."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")

    def _new_partner(self, **vals):
        base = {"name": "Gate Converge Co", "is_company": True, "supplier_rank": 1}
        base.update(vals)
        return self.env["res.partner"].create(base)

    def _new_run(self, partner):
        return self.env["plasticos.enrichment.run"].create({"partner_id": partner.id})

    def test_gate_converge_live_writeback_applies_fields(self):
        partner = self._new_partner()
        run = self._new_run(partner)
        self.assertFalse(partner.website)
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(final_fields={"website": "https://enriched.example", "city": "Raleigh"}),
            ) as gate_call,
        ):
            run.action_execute()
        gate_call.assert_called_once()
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.engine_used, "gate")
        self.assertEqual(partner.website, "https://enriched.example")
        self.assertEqual(partner.city, "Raleigh")

    def test_gate_converge_merge_not_overwrite(self):
        partner = self._new_partner(city="Existing City")
        run = self._new_run(partner)
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(
                    final_fields={"city": "New City", "website": "https://backfill.example"}
                ),
            ),
        ):
            run.action_execute()
        self.assertEqual(partner.city, "Existing City")
        self.assertEqual(partner.website, "https://backfill.example")

    def test_gate_converge_review_only_when_autowriteback_disabled(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("plasticos.gate.auto_writeback", "0")
        self.addCleanup(icp.set_param, "plasticos.gate.auto_writeback", "1")
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(final_fields={"website": "https://enriched.example"}),
            ),
        ):
            run.action_execute()
        self.assertEqual(run.state, "review")
        self.assertEqual(run.engine_used, "gate")
        self.assertFalse(partner.website)

    def test_gate_converge_non_ok_status_degrades_without_local(self):
        run = self._new_run(self._new_partner())
        with (
            patch("odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled", return_value=True),
            patch.object(type(run), "_run_gate_converge", return_value=False),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertEqual(run.engine_used, "gate")
        self.assertEqual(run.state, "degraded")
        self.assertNotEqual(run.state, "injected")

    def test_gate_disabled_fails_closed_no_local(self):
        run = self._new_run(self._new_partner())
        with (
            patch("odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled", return_value=False),
            patch(_SEND, side_effect=AssertionError("Gate must not be called when disabled")),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.failure_class, "permanent")

    def test_gate_failure_degrades_without_local_crawl(self):
        run = self._new_run(self._new_partner())
        with (
            patch("odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled", return_value=True),
            patch.object(type(run), "_run_gate_converge", side_effect=RuntimeError("gate down")),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertEqual(run.engine_used, "gate")
        self.assertIn(run.state, ("retryable", "failed", "degraded"))
