"""Export campaign S3: operation-scoped evidence never opens a claim (RP-05-E022, B9).

Only an exact legacy Claim Pics row opens one claim. An operation row on the
same original, created directly or written onto a pending shell, opens no
claim and sends no notification. Notifications are counted, never sent.
"""

import base64
import itertools
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

GATE = "export_gate_receipt"
_BYTES = itertools.count()


@tagged("post_install", "-at_install", "claims", "scoped_evidence")
class TestDocumentExportEvidence(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Claim Scope Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Claim Scope Supplier", "is_company": True, "parent_id": parent.id, "supplier_rank": 1}
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Claim Scope Buyer", "is_company": True, "parent_id": parent.id, "customer_rank": 1}
        )
        cls.verifier = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Claim Scope Verifier",
                    "login": "s3_claim_scope_verifier",
                    "group_ids": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref("plasticos_documents.group_documents_user").id,
                            ],
                        )
                    ],
                }
            )
        )
        cls.claim_tag = cls.env["plasticos.document.tag"].search([("code", "=", "CLAIM_PHOTO")], limit=1)
        if not cls.claim_tag:
            raise AssertionError("BLOCKED: CLAIM_PHOTO tag is not installed")

    def setUp(self):
        super().setUp()
        self.patch(type(self.env["plasticos.document"]), "_scoped_obligation_kinds", lambda model: frozenset({GATE}))
        self.sent = []
        claim_model = type(self.env["plasticos.claim"])
        self.patch(claim_model, "_send_claim_notification", lambda claim: self.sent.append(claim.id))

    def _load(self, name):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {"name": name, "supplier_id": self.supplier.id, "buyer_id": self.buyer.id, "sale_order_id": order.id}
        )
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(load.transaction_id, tx)
        return tx, load

    def _attachment(self):
        return self.env["ir.attachment"].create(
            {
                "name": "claim-photo.jpg",
                "datas": base64.b64encode(f"claim-photo-{next(_BYTES)}".encode()),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )

    def _shell(self, attachment):
        return self.env["plasticos.document"].create(
            {
                "name": "Claim Pics",
                "tag_id": self.claim_tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )

    def _operation(self, shell, load, revision="BKG-1/r1"):
        return shell.with_user(self.verifier)._associate_scope(
            "plasticos.load",
            load.id,
            "booking mail",
            obligation_kind=GATE,
            operation_revision_key=revision,
            coverage_key="container-1",
        )

    def _claims(self, document):
        return self.env["plasticos.claim"].search([("source_document_id", "=", document.id)])

    def test_operation_row_on_a_pending_shell_opens_no_claim(self):
        """Write path: the operation scope fills the shell; no claim, no notification."""
        _tx, load = self._load("TX-S3-CLAIM-WRITE")
        shell = self._shell(self._attachment())
        row = self._operation(shell, load)
        self.assertEqual(row, shell)
        self.assertEqual(row.association_state, "accepted")
        self.assertFalse(self._claims(row))
        row._check_claim_trigger()
        self.assertFalse(self._claims(row))
        self.assertEqual(self.sent, [])

    def test_one_original_two_links_open_at_most_one_claim(self):
        """Create path: a legacy claim row opens one claim; another operation row adds none."""
        tx, load = self._load("TX-S3-CLAIM-MULTI")
        attachment = self._attachment()
        legacy = (
            self._shell(attachment).with_user(self.verifier).action_associate("plasticos.load", load.id, "buyer photos")
        )
        claims = self._claims(legacy)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims.transaction_id, tx)
        self.assertEqual(claims.load_id, load)
        operation = self._operation(self._shell(attachment), load)
        self.assertNotEqual(operation, legacy)
        self.assertFalse(self._claims(operation))
        again = self._operation(self._shell(attachment), load)
        self.assertEqual(again, operation)
        self.assertEqual(self.env["plasticos.claim"].search_count([("transaction_id", "=", tx.id)]), 1)
        self.assertEqual(self.sent, claims.ids)

    def test_buyerless_operation_evidence_invents_no_claim(self):
        """A load with no transaction has no buyer claim, legacy or operation."""
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertFalse(load.transaction_id)
        operation = self._operation(self._shell(self._attachment()), load)
        self.assertFalse(self._claims(operation))
        self.assertEqual(self.sent, [])

    def test_operation_row_written_later_with_claim_fields_stays_claimless(self):
        """B9 write path: a later write of a watched field on an operation row opens no claim."""
        _tx, load = self._load("TX-S3-CLAIM-LATER")
        row = self._operation(self._shell(self._attachment()), load)
        with patch.object(type(row), "_legacy_claim_subject", side_effect=AssertionError("legacy path reached")):
            row.write({"name": "Claim Pics renamed", "tag_id": self.claim_tag.id})
        self.assertFalse(self._claims(row))
        self.assertEqual(self.sent, [])
