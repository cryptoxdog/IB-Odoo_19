"""One business verification writer. Domain command, direct-write refusal, eligibility."""

import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents.models.document import VERIFICATION_GRANT_KEY
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "documents", "verification")
class TestVerificationWriter(PlasticosTestCase):
    """DOC-V domain writer, provenance, eligibility, and the posting boundary."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Verifier Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        internal = cls.env.ref("base.group_user")
        verifier = cls.env.ref("plasticos_documents.group_documents_user")
        manager = cls.env.ref("plasticos_documents.group_documents_manager")
        cls.verifier = cls.env["res.users"].create(
            {
                "name": "Ordinary Verifier",
                "login": "phase_a_verifier",
                "group_ids": [(6, 0, [internal.id, verifier.id])],
            }
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Documents Manager",
                "login": "phase_a_doc_manager",
                "group_ids": [(6, 0, [internal.id, manager.id])],
            }
        )
        cls.internal = cls.env["res.users"].create(
            {
                "name": "Base Internal",
                "login": "phase_a_base_internal",
                "group_ids": [(6, 0, [internal.id])],
            }
        )
        cls.tag = cls.env["plasticos.document.tag"].create({"name": "Phase A BOL", "code": "PHASE_A_BOL"})
        cls.tx = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.partner.id, "buyer_id": cls.partner.id, "quantity": 1000}
        )

    def _attachment(self, payload=b"original-bytes"):
        return self.env["ir.attachment"].create(
            {
                "name": "evidence.txt",
                "datas": base64.b64encode(payload),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )

    def _document(self, **extra):
        vals = {
            "name": "BOL",
            "tag_id": self.tag.id,
            "res_model": "plasticos.transaction",
            "res_id": self.tx.id,
            "transaction_id": self.tx.id,
            "attachment_id": self._attachment().id,
        }
        vals.update(extra)
        return self.env["plasticos.document"].create(vals)

    def test_verifier_command_records_one_provenance_and_refuses_direct_writes(self):
        doc = self._document()
        doc.with_user(self.verifier).action_verify()
        self.assertTrue(doc.verified)
        self.assertEqual(doc.verified_by, self.verifier)
        self.assertTrue(doc.verified_at)
        self.assertEqual(doc.evidence_digest, doc.attachment_id.checksum)
        stamp = doc.verified_at
        doc.with_user(self.verifier).action_verify()
        self.assertEqual(doc.verified_at, stamp)
        self.assertEqual(doc.verified_by, self.verifier)
        for vals in (
            {"verified": True},
            {"verified_by": self.manager.id},
            {"verified_at": fields.Datetime.now()},
            {"override": True},
            {"override_reason": "forged"},
            {"evidence_digest": "spoof"},
        ):
            with self.assertRaises(AccessError):
                doc.with_user(self.internal).write(vals)
            with self.assertRaises(AccessError):
                doc.with_user(self.verifier).write(vals)
        self.assertEqual(doc.verified_by, self.verifier)
        self.assertFalse(doc.override)
        forged = {VERIFICATION_GRANT_KEY: {"uid": self.verifier.id, "fields": ["verified"]}}
        with self.assertRaises(AccessError):
            doc.with_user(self.verifier).with_context(**forged).write({"verified": False})
        self.assertTrue(doc.verified)

    def test_base_internal_user_cannot_verify(self):
        doc = self._document()
        with self.assertRaises(AccessError):
            doc.with_user(self.internal).action_verify()
        with self.assertRaises(AccessError):
            doc.with_user(self.internal).action_override(reason="not a manager")
        self.assertFalse(doc.verified)
        self.assertFalse(doc.override)
        self.assertFalse(doc.verified_by)
        self.assertFalse(doc.verified_at)

    def test_create_cannot_seed_a_decision(self):
        with self.assertRaises(AccessError):
            self._document(verified=True)
        self.assertFalse(self.env["plasticos.document"].search([("verified", "=", True), ("tag_id", "=", self.tag.id)]))

    def test_partner_only_and_missing_file_stay_unresolved(self):
        partner_doc = self._document(res_model="res.partner", res_id=self.partner.id, transaction_id=False)
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            partner_doc.with_user(self.verifier).action_verify()
        self.assertFalse(partner_doc.verified)
        empty = self._document()
        empty.attachment_id.write({"datas": base64.b64encode(b"")})
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            empty.with_user(self.verifier).action_verify()
        self.assertFalse(empty.verified)

    def test_replaced_expired_inactive_and_superseded_keep_history_and_lose_eligibility(self):
        self.env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")]).write(
            {"active": False}
        )
        self.env["plasticos.document.rule"].create(
            {
                "name": "phase-a-current",
                "tag_id": self.tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": True,
                "required_for_close": True,
            }
        )
        service = self.env["plasticos.compliance.service"]
        old = self._document()
        old.with_user(self.verifier).action_verify()
        stamp = old.verified_at
        actor = old.verified_by
        self.assertTrue(service.is_compliant("plasticos.transaction", self.tx.id))

        old.expiry_date = fields.Date.today() - timedelta(days=1)
        self.assertTrue(old.verified)
        self.assertEqual(old.verified_at, stamp)
        self.assertFalse(old._currently_eligible())
        old._cron_compliance_audit()
        self.assertTrue(old.verified)
        self.assertEqual(old.verified_by, actor)
        self.assertFalse(service.is_compliant("plasticos.transaction", self.tx.id))

        old.expiry_date = False
        self.assertTrue(old._currently_eligible())
        old.attachment_id.write({"datas": base64.b64encode(b"replaced-bytes")})
        self.assertTrue(old.verified)
        self.assertEqual(old.verified_at, stamp)
        self.assertFalse(old._currently_eligible())
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            old.with_user(self.verifier).action_verify()
        self.assertEqual(old.verified_at, stamp)

        replacement = self._document(name="BOL v2", version=2)
        old.action_supersede(replacement.id)
        self.assertFalse(replacement.verified)
        self.assertTrue(old.verified)
        self.assertFalse(old.is_current)
        self.assertFalse(service.is_compliant("plasticos.transaction", self.tx.id))

        current = self._document(name="BOL active")
        current.with_user(self.verifier).action_verify()
        current.active = False
        self.assertTrue(current.verified)
        self.assertFalse(current._currently_eligible())

    def test_override_requires_manager_reason_and_freezes_the_reason(self):
        doc = self._document()
        with self.assertRaises(AccessError):
            doc.with_user(self.verifier).action_override(reason="ordinary user")
        with self.assertRaises(UserError):
            doc.with_user(self.manager).action_override(reason="  ")
        self.assertFalse(doc.override)
        doc.with_user(self.manager).action_override(reason="Customer confirmed the scan")
        self.assertTrue(doc.override)
        self.assertEqual(doc.override_reason, "Customer confirmed the scan")
        self.assertEqual(doc.override_by, self.manager)
        self.assertTrue(doc.override_at)
        stamp = doc.override_at
        doc.with_user(self.manager).action_override(reason="Customer confirmed the scan")
        self.assertEqual(doc.override_at, stamp)
        with self.assertRaises(UserError):
            doc.with_user(self.manager).action_override(reason="changed later")
        self.assertEqual(doc.override_reason, "Customer confirmed the scan")
        with self.assertRaises(AccessError):
            doc.write({"override_reason": "silent edit"})

    def test_document_transition_does_not_post_dispatch_or_mail(self):
        """BRS-POS-03-R008 and BRS-POS-09-R013. Explicit action_post still posts."""
        self.env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")]).write(
            {"active": False}
        )
        self.env["plasticos.document.rule"].create(
            {
                "name": "phase-a-invoice",
                "tag_id": self.tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": True,
                "required_for_close": False,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Buyer", "quantity": 1, "price_unit": 25.0})],
            }
        )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Vendor", "quantity": 1, "price_unit": 10.0})],
            }
        )
        freight = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner.id,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Freight", "quantity": 1, "price_unit": 5.0})],
            }
        )
        self.tx.write(
            {
                "customer_invoice_id": invoice.id,
                "vendor_bill_ids": [(4, bill.id)],
                "freight_bill_ids": [(4, freight.id)],
            }
        )
        doc = self._document()
        mail_before = self.env["mail.mail"].search_count([])
        tx_model = type(self.tx)
        move_model = type(invoice)
        load_model = type(self.env["plasticos.load"])
        with (
            patch.object(tx_model, "_auto_post_pending_invoices", side_effect=AssertionError("autopost")),
            patch.object(move_model, "action_post", side_effect=AssertionError("post")),
            patch.object(load_model, "action_dispatch", side_effect=AssertionError("dispatch")),
        ):
            doc.with_user(self.verifier).action_verify()
            self.tx.invalidate_recordset()
            self.tx._compute_compliance()
        self.assertEqual(self.tx.compliance_status, "compliant")
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(bill.state, "draft")
        self.assertEqual(freight.state, "draft")
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_before)
        invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(bill.state, "draft")
        self.assertEqual(freight.state, "draft")
