"""Odoo runtime tests for Gate-only enrichment converge (M4 / ROAD-GATE-013).

Covers live auto-writeback (default), review-only opt-out, and fail-closed
behavior when converge returns non-ok status or no writable allowlisted fields.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_gate.services.gate_config import (
    GateAvailability,
    GateAvailabilityVerdict,
    GateCapability,
)
from odoo.exceptions import UserError
from odoo.tests.common import tagged

_SEND = "odoo.addons.plasticos_gate.services.gate_client.send_converge_action"
_ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled"
_CLASSIFY = "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability"


def _available_verdict() -> GateAvailabilityVerdict:
    return GateAvailabilityVerdict(
        status=GateAvailability.AVAILABLE,
        available=True,
        capability=GateCapability.ENRICHMENT,
        reasons=[],
        gate_url_configured=True,
    )


def _fake_gate_result(packet_id="pkt-conv-1", correlation_id="corr-conv-1", final_fields=None, status="ok"):
    packet = SimpleNamespace(header=SimpleNamespace(packet_id=packet_id, correlation_id=correlation_id))
    payload = {"status": status, "final_fields": final_fields or {"website": "https://enriched.example"}}
    return {"packet": packet, "payload": payload}


@tagged("post_install", "-at_install", "plasticos", "enrichment", "gate")
class TestGateEnrichmentFallback(PlasticosTestCase):
    """Verify Gate converge live writeback and fail-closed degrade paths."""

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
        """Default (auto_writeback ON): allowlisted fields are written live."""
        partner = self._new_partner()
        run = self._new_run(partner)
        self.assertFalse(partner.website)
        self.assertFalse(partner.city)
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(final_fields={"website": "https://enriched.example", "city": "Raleigh"}),
            ) as gate_call,
        ):
            run.action_execute()
        gate_call.assert_called_once()
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.engine_used, "gate")
        self.assertEqual(run.fields_written, 2)
        self.assertEqual(run.gate_packet_id, "pkt-conv-1")
        self.assertEqual(partner.website, "https://enriched.example")
        self.assertEqual(partner.city, "Raleigh")

    def test_gate_converge_review_only_when_autowriteback_disabled(self):
        """auto_writeback=0: proposal stored for review, partner not written."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("plasticos.gate.auto_writeback", "0")
        self.addCleanup(icp.set_param, "plasticos.gate.auto_writeback", "1")
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, return_value=_fake_gate_result(final_fields={"website": "https://enriched.example"})),
        ):
            run.action_execute()
        self.assertEqual(run.state, "review")
        self.assertEqual(run.engine_used, "gate")
        self.assertFalse(partner.website)
        self.assertEqual(
            run.gate_proposal.get("proposed_partner_fields"),
            {"website": "https://enriched.example"},
        )

    def test_gate_converge_non_ok_status_fails_closed(self):
        """Non-ok EIE status -> degraded UserError; never mark injected."""
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(
                    status="error",
                    final_fields={"website": "https://x.example"},
                ),
            ),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertEqual(run.state, "degraded")
        self.assertNotEqual(run.state, "injected")

    def test_gate_converge_empty_fields_fails_closed(self):
        """status ok but no writable allowlisted fields -> degraded, no fake success."""
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(final_fields={"unknown_key": "x", "notes": "y"}),
            ),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertEqual(run.state, "degraded")
        self.assertNotEqual(run.state, "injected")

    def test_gate_disabled_raises(self):
        """Gate enrichment disabled -> failed UserError (M4: no local crawl fallback)."""
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch(
                _CLASSIFY,
                return_value=GateAvailabilityVerdict(
                    status=GateAvailability.ENRICHMENT_DISABLED,
                    available=False,
                    capability=GateCapability.ENRICHMENT,
                    reasons=["enrichment disabled"],
                    gate_url_configured=True,
                ),
            ),
            patch(_ENABLED, return_value=False),
            patch(_SEND, side_effect=AssertionError("Gate must not be called when disabled")),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertEqual(run.state, "failed")
