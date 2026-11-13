"""No Gate match starts on incomplete material: intake route, lot route, and retry.

The orchestrator is the one funnel every match start goes through
(``run_match_for_intake`` / ``run_match_for_lot``; the intake button and the
match-run retry both call them). The refusal happens before a run exists and
before Gate is addressed, so nothing is written and nothing is sent.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_matching.models.match_run import RECEIPT_WRITE_CONTEXT
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_match_run_receipts import (
    _CLASSIFY,
    _ENABLED,
    _SEND,
    _available_verdict,
    _eligible_candidate,
    _fake_gate_result,
)

_NO_SEND = AssertionError("Gate must not be addressed for incomplete material")


@tagged("post_install", "-at_install", "plasticos", "matching", "gate")
class TestMatchMaterialGate(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_gate_url = os.environ.get("GATE_URL")
        super().setUpClass()
        cls._skip_if_model_missing("plasticos.match.orchestrator", "plasticos.match.run", "plasticos.material.profile")
        os.environ["GATE_URL"] = "https://gate.example.internal"
        cls.supplier = cls._create_partner("Material Gate Supplier", supplier_rank=1)
        cls.buyer = cls._create_partner("Material Gate Buyer", customer_rank=1)
        cls.polymer = cls._get_or_create_polymer()
        cls.form = cls._get_or_create_form()
        cls.profile = cls.env["plasticos.material.profile"].create(
            {"partner_id": cls.supplier.id, "polymer_id": cls.polymer.id, "form_id": cls.form.id}
        )
        cls.Run = cls.env["plasticos.match.run"]
        cls.orchestrator = cls.env["plasticos.match.orchestrator"]

    @classmethod
    def tearDownClass(cls):
        if cls._prior_gate_url is None:
            os.environ.pop("GATE_URL", None)
        else:
            os.environ["GATE_URL"] = cls._prior_gate_url
        super().tearDownClass()

    def _intake(self, **overrides):
        intake = self._create_intake(
            partner=self.supplier, polymer=self.polymer, form=self.form, material_profile_id=self.profile.id
        )
        if overrides:
            intake.write(overrides)
        return intake

    def _gate_open(self, send):
        return (
            patch(_CLASSIFY, return_value=_available_verdict()),
            patch(_ENABLED, return_value=True),
            patch(_SEND, side_effect=send) if isinstance(send, BaseException) else patch(_SEND, return_value=send),
        )

    def _snapshot(self, **overrides):
        snapshot = {
            "supplier_partner_id": self.supplier.id,
            "material_profile_id": self.profile.id,
            "polymer_type": "HDPE",
            "form": "pellet",
        }
        snapshot.update(overrides)
        return {key: value for key, value in snapshot.items() if value is not None}

    # ── intake route ──────────────────────────────────────────

    def test_intake_button_refuses_missing_form_and_sends_nothing(self):
        intake = self._intake(form_id=False)
        classify, enabled, send = self._gate_open(_NO_SEND)
        with classify, enabled, send, self.assertRaisesRegex(UserError, r"cannot be matched: Form not set"):
            intake.action_match_to_buyers()
        self.assertFalse(self.Run.search([("intake_id", "=", intake.id)]), "no run exists for a refused start")
        self.assertEqual(intake.status, "draft")

    def test_intake_button_refuses_missing_polymer(self):
        intake = self._intake(polymer_id=False)
        classify, enabled, send = self._gate_open(_NO_SEND)
        with classify, enabled, send, self.assertRaisesRegex(UserError, r"Polymer not set"):
            intake.action_match_to_buyers()
        self.assertFalse(self.Run.search([("intake_id", "=", intake.id)]))

    def test_orchestrator_refuses_incomplete_intake_directly(self):
        intake = self._intake(polymer_id=False, form_id=False)
        classify, enabled, send = self._gate_open(_NO_SEND)
        with classify, enabled, send, self.assertRaisesRegex(UserError, r"Polymer and Form not set"):
            self.orchestrator.run_match_for_intake(intake)
        self.assertFalse(self.Run.search([("intake_id", "=", intake.id)]))

    def test_retry_of_an_intake_run_is_refused_once_the_material_is_incomplete(self):
        intake = self._intake()
        failed = self.Run.with_context(**{RECEIPT_WRITE_CONTEXT: True}).create(
            {
                "intake_id": intake.id,
                "supplier_partner_id": self.supplier.id,
                "state": "retryable",
                "failure_class": "retryable",
            }
        )
        intake.form_id = False
        classify, enabled, send = self._gate_open(_NO_SEND)
        with classify, enabled, send, self.assertRaisesRegex(UserError, r"Form not set"):
            failed.action_retry_match()
        self.assertEqual(self.Run.search([("intake_id", "=", intake.id)]), failed, "the refused retry made no run")

    def test_complete_intake_still_matches(self):
        intake = self._intake()
        classify, enabled, send = self._gate_open(_fake_gate_result([_eligible_candidate(self.buyer)]))
        with classify, enabled, send as sent:
            run, matches = self.orchestrator.run_match_for_intake(intake)
        self.assertEqual(run.state, "ok")
        self.assertEqual(len(matches), 1)
        query = sent.call_args.kwargs["payload"]["query"]
        self.assertTrue(query["polymer_type"])
        self.assertTrue(query["form"])

    # ── lot route ─────────────────────────────────────────────

    def test_lot_without_polymer_is_refused(self):
        classify, enabled, send = self._gate_open(_NO_SEND)
        with classify, enabled, send, self.assertRaisesRegex(UserError, r"lot cannot be matched: Polymer not set"):
            self.orchestrator.run_match_for_lot(
                supplier_partner_id=self.supplier.id, snapshot=self._snapshot(polymer_type=None)
            )
        self.assertFalse(self.Run.search([("supplier_partner_id", "=", self.supplier.id)]))

    def test_lot_without_form_is_refused(self):
        classify, enabled, send = self._gate_open(_NO_SEND)
        with classify, enabled, send, self.assertRaisesRegex(UserError, r"lot cannot be matched: Form not set"):
            self.orchestrator.run_match_for_lot(supplier_partner_id=self.supplier.id, snapshot=self._snapshot(form=""))
        self.assertFalse(self.Run.search([("supplier_partner_id", "=", self.supplier.id)]))

    def test_complete_lot_still_matches(self):
        classify, enabled, send = self._gate_open(_fake_gate_result([_eligible_candidate(self.buyer)]))
        with classify, enabled, send as sent:
            run, matches = self.orchestrator.run_match_for_lot(
                supplier_partner_id=self.supplier.id, snapshot=self._snapshot()
            )
        self.assertEqual(run.state, "ok")
        self.assertEqual(len(matches), 1)
        query = sent.call_args.kwargs["payload"]["query"]
        self.assertEqual(query["polymer_type"], "HDPE")
        self.assertEqual(query["form"], "pellet")
