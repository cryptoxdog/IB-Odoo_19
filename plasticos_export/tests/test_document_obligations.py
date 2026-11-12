"""Export obligation kinds and release narrowing on the Documents owner (C05 E1, E2; C05-SCOPE-1).

Export declares its four operation obligations and maps each Logistics
operation kind to the ones that gate it. Each operation kind is witnessed end
to end through the frozen ``assert_can_release_physical_operation`` command.
Obligations another owner declares keep the Documents default.
BRS-EXP-03-R002, BRS-EXP-03-R007, BRS-EXP-14-R020.
"""

import base64
import itertools
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents.models.document import PlasticosDocument
from odoo.addons.plasticos_logistics.models.load import PHYSICAL_RELEASE_OPERATIONS
from odoo.tests.common import new_test_user, tagged

from ..models.document_inherit import (
    BOOKING_CONFIRMATION,
    EXPORT_OBLIGATION_KINDS,
    LOADING_PHOTOS,
    TERMINAL_INGATE_RECEIPT,
    VERIFIED_GROSS_MASS,
)

_BYTES = itertools.count(1)
EXPECTED = {
    "schedule": {BOOKING_CONFIRMATION},
    "dispatch": {BOOKING_CONFIRMATION},
    "dispatch_packet": {BOOKING_CONFIRMATION},
    "carrier_document": {BOOKING_CONFIRMATION, VERIFIED_GROSS_MASS},
}


@tagged("post_install", "-at_install", "plasticos", "plasticos_export")
class TestExportDocumentObligations(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_notrack=True))
        cls.Document = cls.env["plasticos.document"]
        cls.verifier = new_test_user(
            cls.env,
            login="s5b_obligation_verifier",
            groups="base.group_user,plasticos_documents.group_documents_user,purchase.group_purchase_user",
        )
        cls.buyer = cls.env["res.partner"].create({"name": "S5B Obligation Buyer", "is_company": True})
        cls.tag = cls.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        if not cls.tag:
            raise AssertionError("BLOCKED: BOL document tag is not installed")

    def _load(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        return self.env["plasticos.load"].create({"sale_order_id": order.id})

    def _stale_evidence(self, load, kind):
        """Accepted, verified evidence of ``kind`` on ``load`` that expires tomorrow."""
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{kind}.pdf",
                "datas": base64.b64encode(f"{kind}-{next(_BYTES)}".encode()),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.Document.create(
            {
                "name": kind,
                "tag_id": self.tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        row = shell.with_user(self.verifier)._associate_scope(
            "plasticos.load",
            load.id,
            f"export {kind}",
            obligation_kind=kind,
            operation_revision_key="BKG-6509024800/r1",
            coverage_key="container-1",
        )
        row.write({"expiry_date": fields.Date.today() + timedelta(days=1)})
        row.with_user(self.verifier).action_verify()
        return row

    def _verdicts(self, load):
        Load = self.env["plasticos.load"]
        later = fields.Date.today() + timedelta(days=5)
        with patch.object(type(self.Document), "_evidence_today", return_value=later):
            return {kind: Load.assert_can_release_physical_operation(load.id, kind)["status"] for kind in EXPECTED}

    def test_export_declares_its_four_obligation_kinds(self):
        """C05 E1: core Documents declares none; Export declares its own by _inherit."""
        declared = self.Document._scoped_obligation_kinds()
        self.assertEqual(
            EXPORT_OBLIGATION_KINDS,
            {BOOKING_CONFIRMATION, VERIFIED_GROSS_MASS, LOADING_PHOTOS, TERMINAL_INGATE_RECEIPT},
        )
        self.assertTrue(EXPORT_OBLIGATION_KINDS <= declared)
        self.assertEqual(set(PHYSICAL_RELEASE_OPERATIONS), set(EXPECTED))

    def test_release_obligations_per_operation_kind(self):
        """C05 E2: each operation kind is gated by exactly the Export obligations it needs."""
        for operation_kind, expected in EXPECTED.items():
            export_part = self.Document._release_obligations(operation_kind) & EXPORT_OBLIGATION_KINDS
            self.assertEqual(export_part, expected, operation_kind)
        self.assertFalse(self.Document._release_obligations("unknown_operation") & EXPORT_OBLIGATION_KINDS)

    def test_other_owners_keep_the_documents_default(self):
        """C05 E2: Export narrows only its own kinds; another owner's kind gates every operation as before."""
        with patch.object(PlasticosDocument, "_scoped_obligation_kinds", lambda model: frozenset({"other_owner_kind"})):
            for operation_kind in EXPECTED:
                self.assertIn("other_owner_kind", self.Document._release_obligations(operation_kind))

    def test_stale_booking_confirmation_withholds_every_release(self):
        """C05 E2 schedule/dispatch/dispatch_packet/carrier_document: a stale carrier confirmation gates all four."""
        load = self._load()
        self._stale_evidence(load, BOOKING_CONFIRMATION)
        self.assertEqual(set(self._verdicts(load).values()), {"blocked"})

    def test_stale_vgm_withholds_only_carrier_documents(self):
        """C05 E2 carrier_document: VGM gates the hand-over of weights only."""
        load = self._load()
        self._stale_evidence(load, VERIFIED_GROSS_MASS)
        self.assertEqual(
            self._verdicts(load),
            {"schedule": "applied", "dispatch": "applied", "dispatch_packet": "applied", "carrier_document": "blocked"},
        )

    def test_after_the_fact_evidence_never_gates_a_new_instruction(self):
        """Operator terminal-handoff decision 2026-11-11: loading photos and the in-gate receipt prove past events."""
        load = self._load()
        self._stale_evidence(load, LOADING_PHOTOS)
        self._stale_evidence(load, TERMINAL_INGATE_RECEIPT)
        self.assertEqual(set(self._verdicts(load).values()), {"applied"})
