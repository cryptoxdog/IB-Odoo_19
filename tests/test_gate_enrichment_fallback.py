"""Odoo runtime tests for Gate-primary enrichment converge (ROAD-GATE-013).

Covers live auto-writeback (default), merge-not-overwrite, review-only opt-out,
and Gate -> local fallback ordering on plasticos.enrichment.run.
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
    """Verify Gate converge live writeback + local fallback on plasticos.enrichment.run."""

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
        """Default (auto_writeback ON): allowlisted fields are written live on sample data."""
        partner = self._new_partner()
        run = self._new_run(partner)
        self.assertFalse(partner.website)
        self.assertFalse(partner.city)
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
        self.assertEqual(run.fields_written, 2)
        self.assertEqual(run.gate_packet_id, "pkt-conv-1")
        self.assertEqual(run.gate_correlation_id, "corr-conv-1")
        # Live writeback landed on the partner
        self.assertEqual(partner.website, "https://enriched.example")
        self.assertEqual(partner.city, "Raleigh")
        # Provenance recorded for audit/rollback
        prov = self.env["plasticos.enrichment.provenance"].search([("run_id", "=", run.id)])
        self.assertEqual(set(prov.mapped("target_field")), {"website", "city"})
        self.assertTrue(all(p.target_model == "res.partner" for p in prov))
        self.assertTrue(all(p.status == "written" for p in prov))

    def test_gate_converge_merge_not_overwrite(self):
        """Existing partner values are never clobbered; only blanks are backfilled."""
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
        self.assertEqual(run.state, "injected")
        self.assertEqual(partner.city, "Existing City")  # preserved
        self.assertEqual(partner.website, "https://backfill.example")  # backfilled
        self.assertEqual(run.fields_written, 1)

    def test_gate_converge_review_only_when_autowriteback_disabled(self):
        """auto_writeback=0 restores review-only: proposal stored, no partner writes."""
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
        self.assertFalse(partner.website)  # not written in review-only mode
        self.assertEqual(
            run.gate_proposal.get("proposed_partner_fields"),
            {"website": "https://enriched.example"},
        )

    def test_gate_converge_non_ok_status_falls_back_to_local(self):
        """A non-ok EIE status is a failure signal -> local fallback, never injected."""
        run = self._new_run(self._new_partner())
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                _SEND,
                return_value={
                    "packet": SimpleNamespace(header=SimpleNamespace(packet_id="p", correlation_id="c")),
                    "payload": {"status": "error", "final_fields": {"website": "https://x.example"}},
                },
            ),
        ):
            # Non-ok -> _run_gate_converge returns False -> local path -> no sources -> UserError
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertNotEqual(run.engine_used, "gate")
        self.assertNotEqual(run.state, "injected")

    def test_gate_converge_empty_fields_falls_back_to_local(self):
        """status ok but no writable allowlisted fields -> fall back, do not fake success."""
        run = self._new_run(self._new_partner())
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(
                _SEND,
                # only non-allowlisted keys -> partner_writeback_from_converge drops all
                return_value=_fake_gate_result(final_fields={"unknown_key": "x", "notes": "y"}),
            ),
        ):
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertNotEqual(run.engine_used, "gate")
        self.assertNotEqual(run.state, "injected")

    def test_gate_disabled_uses_local_pipeline(self):
        run = self._new_run(self._new_partner())
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=False),
            patch(_SEND, side_effect=AssertionError("Gate must not be called when disabled")),
        ):
            # Local path requires sources; none added -> raises (proves local branch entered)
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertNotEqual(run.engine_used, "gate")

    def test_gate_failure_falls_back_to_local(self):
        run = self._new_run(self._new_partner())
        with (
            patch.object(type(run), "_should_try_gate_converge", return_value=True),
            patch(_SEND, side_effect=RuntimeError("gate down")),
        ):
            # Gate raises -> caught -> local path -> no sources -> UserError
            with self.assertRaises(UserError):
                run.action_execute()
        self.assertNotEqual(run.engine_used, "gate")
