"""Gate enrichment action tests. Security does not depend on Gate."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "plasticos", "action", "enrichment")
class TestEnrichmentRunActions(PlasticosTestCase):
    """Tests for plasticos.enrichment.run action/button methods."""

    # Enrichment is Gate-only (M4): action_execute converges through Gate and never
    # crawls locally; on Gate failure it rolls the request back and persists the
    # classified state on an owned cursor (plasticos_enrichment/models/enrichment_run.py:317-441).
    # partner_id is required (enrichment_run.py:26). The Gate transport and availability
    # verdict are the external boundary and are patched; the run's own handling is not.

    _CLASSIFY = "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability"
    _ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled"
    _SEND = "odoo.addons.plasticos_gate.services.gate_client.send_converge_action"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.enrichment.run")
        cls.Run = cls.env["plasticos.enrichment.run"]

    def _make_run(self, partner=None, **kw):
        partner = partner or self._create_partner("Enrichment Run Co", supplier_rank=1)
        vals = {"partner_id": partner.id}
        vals.update(kw)
        return self.Run.create(vals)

    def _verdict(self, available):
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateAvailability,
            GateAvailabilityVerdict,
            GateCapability,
        )

        return GateAvailabilityVerdict(
            status=GateAvailability.AVAILABLE if available else GateAvailability.ENRICHMENT_DISABLED,
            available=available,
            capability=GateCapability.ENRICHMENT,
            reasons=[] if available else ["enrichment disabled"],
            gate_url_configured=True,
        )

    @staticmethod
    def _completed_converge_result():
        """EIE EnrichResponse shape relayed by Gate (mapped by gate_mappers.map_converge_response)."""
        packet = SimpleNamespace(header=SimpleNamespace(packet_id="pkt-act-1", correlation_id="corr-act-1"))
        payload = {
            "state": "completed",
            "failure_reason": None,
            "fields": {"website": "https://enriched.example"},
            "confidence": 0.9,
        }
        return {"packet": packet, "payload": payload}

    @contextmanager
    def _request_rollback(self):
        """Stand in for the RPC request rollback with a savepoint rollback (cr.rollback() is forbidden in tests)."""
        self.registry_enter_test_mode()
        savepoint = self.env.cr.savepoint(flush=True)
        try:
            with patch.object(self.env.cr, "rollback", savepoint.rollback):
                yield
        finally:
            savepoint.close(rollback=False)

    def test_action_execute(self):
        run = self._make_run()
        with (
            patch(self._CLASSIFY, return_value=self._verdict(False)),
            patch(self._ENABLED, return_value=False),
            patch(self._SEND, side_effect=AssertionError("Gate must not be called when disabled")),
            self._request_rollback(),
        ):
            # Not self.assertRaises: its savepoint would undo the durable failure write.
            try:
                run.action_execute()
            except UserError:
                pass
            else:
                self.fail("UserError not raised")
        run.invalidate_recordset()
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.failure_class, "permanent")

    def test_action_inject(self):
        partner = self._create_partner("Enrichment Inject Co", supplier_rank=1)
        proposed = {"website": "https://enriched.example"}
        run = self._make_run(
            partner=partner,
            engine_used="gate",
            state="review",
            gate_proposal={"final_fields": proposed, "proposed_partner_fields": proposed},
            gate_packet_id="pkt-act-inject",
        )
        run.action_inject()
        self.assertEqual(run.state, "injected")
        self.assertEqual(run.fields_written, 1)
        self.assertEqual(partner.website, "https://enriched.example")

    def test_action_run_inference(self):
        # Local inference was retired in M4 and now refuses (enrichment_run.py:741-743).
        run = self._make_run(state="injected")
        with self.assertRaises(UserError):
            run.action_run_inference()

    def test_action_retry_from_error(self):
        run = self._make_run(state="failed")
        with (
            patch(self._CLASSIFY, return_value=self._verdict(True)),
            patch(self._ENABLED, return_value=True),
            patch(self._SEND, return_value=self._completed_converge_result()),
        ):
            run.action_retry_enrichment()
        self.assertNotIn(run.state, ("failed", "retryable", "degraded"))
        self.assertEqual(run.gate_attempt, 2)

    def test_action_cancel(self):
        run = self._make_run()
        if hasattr(run, "action_cancel"):
            run.action_cancel()
            self.assertEqual(run.state, "cancelled")


@tagged("post_install", "-at_install", "plasticos", "error_handling", "api")
class TestEnrichmentApiFailure(PlasticosTestCase):
    def test_enrichment_api_failure_caught(self):
        """A Gate converge transport failure fails closed: UserError, run durably ``degraded``.

        Enrichment is Gate-only (M4); the local crawl it once patched is gone. The run
        rolls the request back and persists the classified state on an owned cursor
        (plasticos_enrichment/models/enrichment_run.py:317-347, :427-441). partner_id is
        required (enrichment_run.py:26).
        """
        if "plasticos.enrichment.run" not in self.env:
            self.skipTest("Enrichment not installed")
        from odoo.addons.plasticos_gate.services.gate_config import (
            GateAvailability,
            GateAvailabilityVerdict,
            GateCapability,
        )

        available = GateAvailabilityVerdict(
            status=GateAvailability.AVAILABLE,
            available=True,
            capability=GateCapability.ENRICHMENT,
            reasons=[],
            gate_url_configured=True,
        )
        partner = self._create_partner("Enrichment API Down", supplier_rank=1)
        run = self.env["plasticos.enrichment.run"].create({"partner_id": partner.id})
        # The durable failure write opens pool.cursor(); in test mode that wraps this cursor.
        self.registry_enter_test_mode()
        savepoint = self.env.cr.savepoint(flush=True)
        raised = False
        try:
            with (
                patch(
                    "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability",
                    return_value=available,
                ),
                patch("odoo.addons.plasticos_gate.services.gate_config.gate_enrichment_enabled", return_value=True),
                patch(
                    "odoo.addons.plasticos_gate.services.gate_client.send_converge_action",
                    side_effect=Exception("API down"),
                ),
                # Stand in for the RPC request rollback (cr.rollback() is forbidden in tests).
                patch.object(self.env.cr, "rollback", savepoint.rollback),
            ):
                # Not self.assertRaises: its savepoint would undo the durable failure write.
                try:
                    run.action_execute()
                except UserError:
                    raised = True
        finally:
            savepoint.close(rollback=False)
        self.assertTrue(raised, "Gate transport failure must surface as UserError")
        run.invalidate_recordset()
        self.assertEqual(run.state, "degraded")
        self.assertIn("API down", " ".join(run.validation_issues or []))
