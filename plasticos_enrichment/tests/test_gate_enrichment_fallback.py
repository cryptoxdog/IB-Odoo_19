"""Odoo runtime tests for Gate-only enrichment converge (M4 / ROAD-GATE-013).

Loaded via plasticos_enrichment/tests for `make test-module m=plasticos_enrichment`.
Covers live auto-writeback (default), review-only opt-out, and fail-closed
behavior when converge returns non-ok status or no writable allowlisted fields.
Failure-path tests invalidate after UserError so assertions see state persisted
outside the request transaction (see EnrichmentRun._persist_operator_state).
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


def _fake_gate_result(
    packet_id="pkt-conv-1",
    correlation_id="corr-conv-1",
    final_fields=None,
    state="completed",
    failure_reason=None,
):
    """The exact EIE EnrichResponse shape Gate relays (mapped by map_converge_response).

    ``state="completed"`` with no ``failure_reason`` is the only usable result;
    the previous fixture used a ``status``/``final_fields`` shape EIE never
    emits, so these tests passed against a payload production never sees.
    """
    packet = SimpleNamespace(header=SimpleNamespace(packet_id=packet_id, correlation_id=correlation_id))
    payload = {
        "state": state,
        "failure_reason": failure_reason,
        "fields": final_fields if final_fields is not None else {"website": "https://enriched.example"},
        "confidence": 0.91,
        "tokens_used": 1840,
        "pass_count": 2,
        "variation_count": 8,
        "inference_version": "v3.0.0-convergence",
        "kb_content_hash": "a3f9b2c1",
    }
    return {"packet": packet, "payload": payload}


def _set_auto_writeback(test, value):
    icp = test.env["ir.config_parameter"].sudo()
    previous = icp.get_param("plasticos.gate.auto_writeback") or "0"
    icp.set_param("plasticos.gate.auto_writeback", value)
    test.addCleanup(icp.set_param, "plasticos.gate.auto_writeback", previous)


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
        """auto_writeback=1 (opt-in; the seed default is 0): allowlisted fields are written live."""
        _set_auto_writeback(self, "1")
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
        self.assertEqual(run.gate_attempt, 1)
        provenance = run.gate_proposal.get("eie_provenance") or {}
        self.assertEqual(provenance.get("confidence"), 0.91)
        self.assertEqual(provenance.get("tokens_used"), 1840)

    def test_gate_converge_review_only_when_autowriteback_disabled(self):
        """auto_writeback=0 (the seed default): proposal stored for review, partner not written."""
        _set_auto_writeback(self, "0")
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
        """Non-ok EIE status -> degraded UserError; state survives request rollback."""
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(
                _SEND,
                return_value=_fake_gate_result(
                    state="failed",
                    failure_reason="no_valid_responses",
                    final_fields={"website": "https://x.example"},
                ),
            ),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        run.invalidate_recordset()
        self.assertEqual(run.state, "degraded")
        self.assertNotEqual(run.state, "injected")

    def test_gate_converge_empty_fields_fails_closed(self):
        """state completed but no writable allowlisted fields -> degraded in BOTH modes."""
        _set_auto_writeback(self, "0")
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
        run.invalidate_recordset()
        self.assertEqual(run.state, "degraded")
        self.assertNotEqual(run.state, "injected")

    def test_operator_retry_advances_the_operation_attempt(self):
        """A retry is a new logical operation: Gate caches per identity, failures included."""
        partner = self._new_partner()
        run = self._new_run(partner)
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, return_value=_fake_gate_result(state="failed", failure_reason="no_valid_responses")),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        run.invalidate_recordset()
        self.assertEqual(run.state, "degraded")
        self.assertEqual(run.gate_attempt, 1)
        sent_keys = []

        def _capture(env, **kwargs):
            sent_keys.append(kwargs.get("idempotency_key"))
            return _fake_gate_result(final_fields={"website": "https://enriched.example"})

        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, side_effect=_capture),
        ):
            run.action_retry_enrichment()
        self.assertEqual(run.gate_attempt, 2)
        self.assertEqual(len(sent_keys), 1)
        self.assertTrue(sent_keys[0].endswith(":attempt-2"), sent_keys[0])

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
        run.invalidate_recordset()
        self.assertEqual(run.state, "failed")
