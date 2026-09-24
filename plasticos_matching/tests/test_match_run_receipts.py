"""Odoo database tests for durable Gate match failure receipts and server-owned receipt evidence.

Loaded via plasticos_matching/tests for ``--test-tags /plasticos_matching``.

Two Odoo 19 test-harness facts shape the failure-path tests here:

* ``TransactionCase`` forbids ``cr.rollback()`` on the test cursor, so the
  ambient RPC rollback the orchestrator performs is stood in for by a rollback
  to a savepoint taken just before the call (``_request_rollback``). That
  discards everything the failing request wrote exactly as the RPC layer
  would, while the owned second cursor keeps its committed rows visible.
* ``TransactionCase`` no longer puts the registry in test mode by itself, so
  ``registry.cursor()`` would open a real second connection that cannot see
  the uncommitted fixture. The class enters registry test mode explicitly
  (``registry_enter_test_mode_cls``), which makes the owned cursor a
  ``TestCursor`` over the test connection. Odoo's own ``assertRaises`` wraps
  its block in a savepoint that would then discard the durable write, so the
  failure paths use the savepoint-free ``_raises`` helper instead.

These tests therefore prove failure classification, the re-created durable
run, that no result persistence, local scoring or commercial mutation happens,
and the operator note. Real cross-session durability is proven by
``tests/runtime_gates/run_c9_c10_matching_failures.py`` (gates C9/C10).
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_gate.services.gate_config import (
    GateAvailability,
    GateAvailabilityVerdict,
    GateCapability,
    GateIntegrationError,
)
from odoo.addons.plasticos_matching.models.match_orchestrator import _canonical_digest
from odoo.addons.plasticos_matching.models.match_run import RECEIPT_FIELDS, RECEIPT_WRITE_CONTEXT
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

_SEND = "odoo.addons.plasticos_gate.services.gate_client.send_match_action"
_ENABLED = "odoo.addons.plasticos_gate.services.gate_config.gate_matching_enabled"
_CLASSIFY = "odoo.addons.plasticos_gate.services.gate_config.classify_gate_availability"
_PERSIST = "odoo.addons.plasticos_matching.models.match_result_writer.PlasticosMatchResultWriter.persist_match_lines"
_NO_PERSIST = AssertionError("canonical result persistence must never run on a failed Gate match")
_NO_SEND = AssertionError("Gate must not be called when matching is disabled")


def _available_verdict() -> GateAvailabilityVerdict:
    return GateAvailabilityVerdict(
        status=GateAvailability.AVAILABLE,
        available=True,
        capability=GateCapability.MATCHING,
        reasons=[],
        gate_url_configured=True,
    )


def _disabled_verdict() -> GateAvailabilityVerdict:
    return GateAvailabilityVerdict(
        status=GateAvailability.MATCHING_DISABLED,
        available=False,
        capability=GateCapability.MATCHING,
        reasons=["plasticos.gate.matching_enabled is off"],
        gate_url_configured=True,
    )


def _fake_gate_result(candidates=None, packet_id="pkt-match-1", correlation_id="corr-match-1"):
    """The CEG match payload shape Gate relays (mapped by map_match_response)."""
    packet = SimpleNamespace(header=SimpleNamespace(packet_id=packet_id, correlation_id=correlation_id))
    payload = {
        "status": "ok",
        "direction": "intake_to_buyer",
        "top_n": 20,
        "candidates": list(candidates or []),
        "query_id": "query-1",
        "contract_version": "contract-1",
        "domain_spec_version": "domain-1",
        "model_version": "model-1",
    }
    return {"packet": packet, "payload": payload}


def _eligible_candidate(buyer, score=0.85):
    return {
        "entity_ref": f"res.partner:{buyer.id}",
        "eligible": True,
        "score": score,
        "score_scale": "0_to_1",
        "rank": 1,
        "explanation": "Eligible Gate candidate",
        "failed_gates": [],
    }


@tagged("post_install", "-at_install", "plasticos", "matching", "gate")
class TestMatchRunReceipts(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._skip_if_model_missing(
            "plasticos.match.orchestrator",
            "plasticos.match.run",
            "plasticos.match.result",
            "plasticos.material.profile",
        )
        # The orchestrator's durable failure write opens registry.cursor(); in
        # test mode that is a TestCursor over this test's connection.
        cls.registry_enter_test_mode_cls()
        cls.env["ir.config_parameter"].sudo().set_param("plasticos.matching_engine.enabled", "1")
        cls.supplier = cls._create_partner("Gate Receipt Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Gate Receipt Buyer", customer_rank=1)
        polymer = cls._get_or_create_polymer()
        form = cls._get_or_create_form()
        cls.profile = cls.env["plasticos.material.profile"].create(
            {"partner_id": cls.supplier.id, "polymer_id": polymer.id, "form_id": form.id}
        )
        cls.intake = cls._create_intake(
            partner=cls.supplier, polymer=polymer, form=form, material_profile_id=cls.profile.id
        )
        cls.Run = cls.env["plasticos.match.run"]
        cls.ServerRun = cls.Run.with_context(**{RECEIPT_WRITE_CONTEXT: True})
        cls.Result = cls.env["plasticos.match.result"]
        cls.orchestrator = cls.env["plasticos.match.orchestrator"]

    # ── helpers ───────────────────────────────────────────────

    @contextmanager
    def _request_rollback(self):
        """Stand in for the RPC rollback: roll back to a savepoint instead of the forbidden cr.rollback()."""
        savepoint = self.env.cr.savepoint(flush=True)
        try:
            with patch.object(self.env.cr, "rollback", savepoint.rollback):
                yield
        finally:
            savepoint.close(rollback=False)

    @contextmanager
    def _raises(self, exc_type):
        """Expect ``exc_type`` without Odoo's assertRaises savepoint, which would undo the durable write."""
        holder = SimpleNamespace(exception=None)
        try:
            yield holder
        except exc_type as exc:
            holder.exception = exc
            return
        self.fail(f"{exc_type.__name__} not raised")

    def _runs(self):
        return self.Run.search([("intake_id", "=", self.intake.id)], order="id")

    def _commercial_snapshot(self):
        self.env.invalidate_all()
        return (
            self.intake.status,
            self.intake.match_count,
            self.intake.best_match_score,
            len(self.intake.match_line_ids),
            self.supplier.supplier_rank,
            self.supplier.customer_rank,
            self.buyer.customer_rank,
            self.Result.search_count([("intake_id", "=", self.intake.id)]),
        )

    def _intake_note(self, run):
        return self.env["mail.message"].search(
            [
                ("model", "=", "plasticos.intake"),
                ("res_id", "=", self.intake.id),
                ("body", "ilike", f"match run {run.id}."),
            ]
        )

    def _server_run(self, **extra):
        vals = {"intake_id": self.intake.id, "supplier_partner_id": self.supplier.id, "state": "ok"}
        vals.update(extra)
        return self.ServerRun.create(vals)

    # ── F192-01: durable failure receipts ──────────────────────

    def test_gate_disabled_failure_receipt_survives_the_request_rollback(self):
        before = self._commercial_snapshot()
        with (
            patch(_CLASSIFY, return_value=_disabled_verdict()),
            patch(_ENABLED, return_value=False),
            patch(_SEND, side_effect=_NO_SEND),
            patch(_PERSIST, side_effect=_NO_PERSIST),
            self._request_rollback(),
            self._raises(UserError) as caught,
        ):
            self.intake.action_match_to_buyers()
        run = self._runs()
        self.assertEqual(len(run), 1)
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.failure_class, "permanent")
        self.assertEqual(run.availability_status, "matching_disabled")
        self.assertEqual(run.engine, "gate")
        self.assertEqual(run.request_attempt, 1)
        self.assertFalse(run.operation_id)
        self.assertIn(f"match run {run.id}", str(caught.exception))
        self.assertTrue(self._intake_note(run))
        self.assertEqual(self._commercial_snapshot(), before)

    def test_transport_failure_is_retryable_receipt_bound_and_retry_advances_the_attempt(self):
        before = self._commercial_snapshot()
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, side_effect=GateIntegrationError("GateTimeoutError", failure_class="retryable")) as send,
            patch(_PERSIST, side_effect=_NO_PERSIST),
            self._request_rollback(),
            self._raises(UserError),
        ):
            self.intake.action_match_to_buyers()
        first = self._runs()
        self.assertEqual(len(first), 1)
        self.assertEqual(first.state, "retryable")
        self.assertEqual(first.failure_class, "retryable")
        self.assertEqual(first.availability_status, "available")
        self.assertTrue(first.operation_id.startswith("odoo:matching:"))
        self.assertEqual(len(first.request_fingerprint), 64)
        self.assertFalse(first.gate_packet_id)
        self.assertFalse(first.gate_response_digest)
        send.assert_called_once()
        self.assertEqual(send.call_args.kwargs["idempotency_key"], first.operation_id)
        self.assertTrue(self._intake_note(first))

        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, side_effect=GateIntegrationError("GateConnectionError", failure_class="retryable")) as retry,
            patch(_PERSIST, side_effect=_NO_PERSIST),
            self._request_rollback(),
            self._raises(UserError),
        ):
            self.intake.action_retry_latest_match()
        runs = self._runs()
        self.assertEqual(len(runs), 2)
        second = runs - first
        self.assertEqual(second.retry_of_id, first)
        self.assertEqual(second.request_attempt, 2)
        self.assertEqual(second.state, "retryable")
        self.assertTrue(second.operation_id.endswith(":attempt-2"), second.operation_id)
        self.assertNotEqual(second.operation_id, first.operation_id)
        self.assertEqual(retry.call_args.kwargs["idempotency_key"], second.operation_id)
        self.assertEqual(self._commercial_snapshot(), before)

    def test_unexpected_transport_exception_is_classified_unknown_and_degraded(self):
        before = self._commercial_snapshot()
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, side_effect=RuntimeError("socket closed mid-handshake")),
            patch(_PERSIST, side_effect=_NO_PERSIST),
            self._request_rollback(),
            self._raises(UserError),
        ):
            self.intake.action_match_to_buyers()
        run = self._runs()
        self.assertEqual(len(run), 1)
        self.assertEqual(run.state, "degraded")
        self.assertEqual(run.failure_class, "unknown")
        self.assertIn("socket closed", run.error_message)
        self.assertTrue(run.operation_id)
        self.assertEqual(self._commercial_snapshot(), before)

    def test_persistence_failure_after_a_gate_answer_keeps_the_gate_receipt_durably(self):
        before = self._commercial_snapshot()
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, return_value=_fake_gate_result([_eligible_candidate(self.buyer)])),
            patch(_PERSIST, side_effect=ValidationError("persisted result conflicts with the receipt")),
            self._request_rollback(),
            self._raises(ValidationError),
        ):
            self.intake.action_match_to_buyers()
        run = self._runs()
        self.assertEqual(len(run), 1)
        self.assertEqual(run.state, "failed")
        self.assertEqual(run.failure_class, "permanent")
        self.assertIn("conflicts with the receipt", run.error_message)
        # Gate answered: the receipt it produced is evidence and survives the rollback.
        self.assertTrue(run.operation_id)
        self.assertEqual(run.gate_packet_id, "pkt-match-1")
        self.assertEqual(run.gate_correlation_id, "corr-match-1")
        self.assertEqual(len(run.gate_response_digest), 64)
        self.assertEqual(run.gate_query_id, "query-1")
        self.assertEqual(run.gate_model_version, "model-1")
        self.assertEqual(run.match_count, 1)
        self.assertTrue(self._intake_note(run))
        self.assertEqual(self._commercial_snapshot(), before)

    # ── success paths: zero-candidate receipt, idempotent Gate-originated results ──

    def test_zero_candidate_gate_response_is_a_valid_durable_ok_receipt(self):
        fake = _fake_gate_result([])
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, return_value=fake),
        ):
            self.intake.action_match_to_buyers()
        run = self._runs()
        self.assertEqual(len(run), 1)
        self.assertEqual(run.state, "ok")
        self.assertEqual(run.match_count, 0)
        self.assertFalse(run.failure_class)
        self.assertTrue(run.operation_id)
        self.assertEqual(run.gate_packet_id, "pkt-match-1")
        self.assertEqual(run.gate_response_digest, _canonical_digest(fake["payload"]))
        self.assertEqual(run.gate_query_id, "query-1")
        self.assertEqual(run.gate_contract_version, "contract-1")
        self.assertEqual(run.gate_domain_spec_version, "domain-1")
        self.assertEqual(run.gate_model_version, "model-1")
        self.assertEqual(self.Result.search_count([("intake_id", "=", self.intake.id)]), 0)
        self.assertEqual(self.intake.status, "draft")
        self.assertFalse(self.intake.match_line_ids)

    def test_successful_match_persists_gate_originated_results_idempotently(self):
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, return_value=_fake_gate_result([_eligible_candidate(self.buyer)])),
        ):
            run, matches = self.orchestrator.run_match_for_intake(self.intake)
        self.assertEqual(run.state, "ok")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["buyer_id"], self.buyer.id)
        self.orchestrator.persist_review_results(self.intake, matches, run)
        self.orchestrator.persist_review_results(self.intake, matches, run)
        results = self.Result.search([("intake_id", "=", self.intake.id)])
        self.assertEqual(len(results), 1)
        self.assertEqual(results.match_run_id, run)
        self.assertEqual(results.run_id, run.operation_id)
        self.assertEqual(results.buyer_partner_id, self.buyer)
        self.assertEqual(results.score, 85.0)
        self.assertEqual(results.model_version, "model-1")
        self.assertEqual(results.score_breakdown["gate_packet_id"], "pkt-match-1")
        self.assertEqual(len(self.intake.match_line_ids), 1)

    # ── F192-04: receipt metadata is server-owned immutable evidence ──

    def test_receipt_fields_refuse_ordinary_and_sudo_writes(self):
        run = self._server_run(
            operation_id="odoo:matching:db:plasticos.match.run:1",
            request_fingerprint="a" * 64,
            gate_response_digest="b" * 64,
            gate_packet_id="packet-1",
            gate_correlation_id="correlation-1",
            gate_query_id="query-1",
            gate_contract_version="contract-1",
            gate_domain_spec_version="domain-1",
            gate_model_version="model-1",
        )
        plain = self.Run.browse(run.id)
        for field_name in RECEIPT_FIELDS:
            tampered = 9 if field_name == "request_attempt" else "tampered"
            with self.subTest(field=field_name), self.assertRaises(AccessError):
                plain.write({field_name: tampered})
            with self.subTest(field=field_name, sudo=True), self.assertRaises(AccessError):
                plain.sudo().write({field_name: tampered})
        plain.write({"error_message": "operator annotation"})
        self.assertEqual(plain.error_message, "operator annotation")
        self.assertEqual(plain.gate_query_id, "query-1")

    def test_receipt_fields_are_write_once_even_through_the_server_door(self):
        run = self._server_run(operation_id="op-1")
        with self.assertRaises(AccessError):
            run.write({"operation_id": "op-2"})
        with self.assertRaises(AccessError):
            run.write({"operation_id": False})
        run.write({"operation_id": "op-1"})  # idempotent rewrite of the same evidence is not a mutation
        run.write({"gate_query_id": "query-1"})  # first capture of an empty receipt slot
        with self.assertRaises(AccessError):
            run.write({"gate_query_id": "query-2"})
        with self.assertRaises(AccessError):
            run.write({"request_attempt": 2})
        self.assertEqual(run.operation_id, "op-1")
        self.assertEqual(run.gate_query_id, "query-1")
        self.assertEqual(run.request_attempt, 1)

    def test_receipt_create_requires_the_server_door(self):
        with self.assertRaises(AccessError):
            self.Run.create(
                {"intake_id": self.intake.id, "supplier_partner_id": self.supplier.id, "operation_id": "op-1"}
            )
        plain = self.Run.create({"intake_id": self.intake.id, "supplier_partner_id": self.supplier.id})
        self.assertEqual(plain.state, "pending")
        self.assertEqual(plain.request_attempt, 1)

    def test_copy_never_carries_receipt_evidence(self):
        run = self._server_run(
            operation_id="op-1",
            request_fingerprint="a" * 64,
            gate_response_digest="b" * 64,
            gate_query_id="query-1",
            request_attempt=3,
        )
        duplicate = self.Run.browse(run.id).copy()
        self.assertNotEqual(duplicate, run)
        for field_name in RECEIPT_FIELDS:
            if field_name == "request_attempt":
                self.assertEqual(duplicate.request_attempt, 1)
            else:
                self.assertFalse(duplicate[field_name], field_name)

    def test_human_review_disposition_stays_mutable_while_the_receipt_does_not(self):
        with (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, return_value=_fake_gate_result([_eligible_candidate(self.buyer)])),
        ):
            self.intake.action_match_to_buyers()
        run = self._runs()
        result = self.Result.search([("intake_id", "=", self.intake.id)])
        self.assertEqual(len(result), 1)
        result.action_accept()
        self.assertEqual(result.state, "accepted")
        self.assertEqual(result.reviewed_by, self.env.user)
        with self.assertRaises(UserError):
            result.write({"score": 1.0})
        with self.assertRaises(AccessError):
            self.Run.browse(run.id).write({"gate_query_id": "rewritten"})
        self.assertEqual(run.gate_query_id, "query-1")
