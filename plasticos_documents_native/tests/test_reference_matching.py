"""B5 deterministic reference matching from the email itself."""

import base64

from markupsafe import Markup

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged

from ..models.reference_match import extract_tokens, number_pattern, split_email_body

SUMMARY = "Document association needs review"


@tagged("post_install", "-at_install", "documents", "integrity_controls")
class TestReferenceFormats(PlasticosTestCase):
    """Patterns come from sequence definitions; nothing else is a reference."""

    def test_pattern_follows_the_sequence_definition(self):
        pattern = number_pattern("SM-%(y)s-", "", 5)
        found = extract_tokens(
            "RE: SM-26-11101, SM-26-1110, SM-2026-11101, XSM-26-22222, SM-26-33333X", [("t", pattern)]
        )
        self.assertEqual(found, [("t", "SM-26-11101")])
        self.assertEqual(extract_tokens("SM-26-123456", [("t", pattern)]), [("t", "SM-26-123456")])

    def test_unknown_placeholder_or_bare_number_gives_no_pattern(self):
        self.assertIsNone(number_pattern("", "", 5))
        self.assertIsNone(number_pattern("%(y)s", "", 5))
        self.assertIsNone(number_pattern("A%(bogus)s-", "", 5))
        self.assertIsNone(number_pattern("A%d", "", 5))

    def test_quoted_text_is_separated_from_fresh_text(self):
        fresh, quoted = split_email_body("<p>New S00012</p><blockquote>Old S00001</blockquote>")
        self.assertIn("S00012", fresh)
        self.assertNotIn("S00001", fresh)
        self.assertIn("S00001", quoted)
        fresh, quoted = split_email_body("New S00012\n> Old S00001\n---------- Forwarded message ---------\nS00099")
        self.assertIn("S00012", fresh)
        self.assertNotIn("S00001", fresh)
        self.assertNotIn("S00099", fresh)
        self.assertIn("S00099", quoted)

    def test_live_patterns_match_real_record_names(self):
        service = self.env["plasticos.document.sync"]
        partner = self.env["res.partner"].create({"name": "B5 Format Partner", "is_company": True})
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1}
        )
        sale = self.env["sale.order"].create({"partner_id": partner.id})
        purchase = self.env["purchase.order"].create({"partner_id": partner.id})
        patterns = service._reference_patterns(self.env.company)
        text = f"{tx.name} {sale.name} {purchase.name}"
        found = dict(extract_tokens(text, patterns))
        self.assertEqual(found.get("plasticos.transaction"), tx.name)
        self.assertEqual(found.get("sale.order"), sale.name)
        self.assertEqual(found.get("purchase.order"), purchase.name)


@tagged("post_install", "-at_install", "documents", "integrity_controls")
class TestReferenceResolution(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        cls.service = cls.env["plasticos.document.sync"]
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "B5 Trucker", "is_company": True, "supplier_rank": 1})
        internal = cls.env.ref("base.group_user")
        manager_group = cls.env.ref("plasticos_security_base.group_operations_manager")
        cls.manager = cls.env["res.users"].create(
            {
                "name": "B5 Operations Manager",
                "login": "b5_ops_manager",
                "group_ids": [(6, 0, [internal.id, manager_group.id])],
            }
        )
        cls.tx_a = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.partner.id, "buyer_id": cls.partner.id, "quantity": 1}
        )
        cls.tx_b = cls.env["plasticos.transaction"].create(
            {"supplier_id": cls.partner.id, "buyer_id": cls.partner.id, "quantity": 2}
        )
        cls.sale = cls.env["sale.order"].create({"partner_id": cls.partner.id})
        cls.company_b = cls.env["res.company"].create({"name": "B5 Other Company"})
        cls.purchase_b = (
            cls.env["purchase.order"]
            .with_company(cls.company_b)
            .create({"partner_id": cls.partner.id, "company_id": cls.company_b.id})
        )
        cls.folder = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")

    def _resolve(self, subject="", body="", company=None):
        fresh, quoted = split_email_body(body)
        return self.service.resolve_references(
            company or self.company, [("email subject", subject), ("email body", fresh)], quoted
        )

    # ── Resolver ─────────────────────────────────────────────
    def test_one_transaction_number_resolves_to_that_transaction(self):
        found = self._resolve(subject=f"POD for {self.tx_a.name}")
        self.assertEqual(found["status"], "one")
        self.assertEqual(found["subject"], self.tx_a)
        self.assertIn(self.tx_a.name, found["detail"])

    def test_same_number_in_subject_and_body_is_one(self):
        found = self._resolve(subject=self.tx_a.name, body=f"<p>Attached for {self.tx_a.name}</p>")
        self.assertEqual(found["status"], "one")
        self.assertEqual(found["subject"], self.tx_a)

    def test_two_different_transactions_in_the_subject_conflict(self):
        found = self._resolve(subject=f"{self.tx_a.name} and {self.tx_b.name}")
        self.assertEqual(found["status"], "conflicting")
        self.assertIsNone(found["subject"])
        self.assertIn(self.tx_a.name, found["detail"])
        self.assertIn(self.tx_b.name, found["detail"])

    def test_sale_order_without_a_transaction_resolves_to_the_order(self):
        found = self._resolve(subject=f"Invoice for {self.sale.name}")
        self.assertEqual(found["status"], "one")
        self.assertEqual(found["subject"], self.sale)

    def test_order_and_unrelated_transaction_conflict(self):
        found = self._resolve(subject=f"{self.sale.name} / {self.tx_a.name}")
        self.assertEqual(found["status"], "conflicting")

    def test_record_in_another_company_is_not_a_match(self):
        found = self._resolve(subject=f"Bill for {self.purchase_b.name}")
        self.assertEqual(found["status"], "none")
        self.assertFalse(found["matches"])
        own = self._resolve(subject=f"Bill for {self.purchase_b.name}", company=self.company_b)
        self.assertEqual(own["status"], "one")
        self.assertEqual(own["subject"], self.purchase_b)

    def test_near_miss_tokens_do_not_match(self):
        for text in (
            self.tx_a.name.lower(),
            f"X{self.tx_a.name}",
            f"{self.tx_a.name}9",
            self.tx_a.name.replace("-", " "),
            "SM-00-00000",
            "no reference here 12345",
        ):
            with self.subTest(text=text):
                self.assertEqual(self._resolve(subject=text)["status"], "none")

    def test_forward_with_older_quoted_reference_uses_the_fresh_one(self):
        body = (
            f"<p>Please file under {self.tx_a.name}</p>"
            f"<blockquote>From: dispatcher<br/>Subject: old load {self.tx_b.name}</blockquote>"
        )
        found = self._resolve(subject="Fwd: paperwork", body=body)
        self.assertEqual(found["status"], "one")
        self.assertEqual(found["subject"], self.tx_a)

    def test_reference_only_in_the_forwarded_part_is_still_read(self):
        body = f"<p>see below</p><blockquote>Subject: BOL {self.tx_b.name}</blockquote>"
        found = self._resolve(subject="Fwd: paperwork", body=body)
        self.assertEqual(found["status"], "one")
        self.assertEqual(found["subject"], self.tx_b)
        self.assertIn("quoted text", found["detail"])

    def test_unknown_company_in_a_multi_company_database_resolves_nothing(self):
        found = self.service.resolve_references(self.env["res.company"], [("email subject", self.tx_a.name)], "")
        self.assertEqual(found["status"], "none")
        self.assertIn("company is unknown", found["detail"])

    # ── Documents ────────────────────────────────────────────
    def _native(self, name="pod.pdf"):
        return self.env["documents.document"].create(
            {
                "name": name,
                "folder_id": self.folder.id,
                "datas": base64.b64encode(b"%PDF-1.4 b5"),
                "doc_type": "bol",
                "company_id": self.company.id,
            }
        )

    def _email(self, record, subject, body="", author=None):
        return record.message_post(
            message_type="email",
            subtype_xmlid="mail.mt_comment",
            subject=subject,
            # An inbound email body is HTML. A plain str would be escaped as text by message_post.
            body=Markup(body),
            email_from="trucker@example.com",
            author_id=self.partner.id if author is None else author.id,
        )

    def test_document_email_with_one_reference_prefills_the_pending_row(self):
        native = self._native()
        shell = native.plasticos_doc_id
        accepted_before = self.env["plasticos.document"].search_count([("association_state", "=", "accepted")])
        message = self._email(native, f"POD {self.tx_a.name}")
        self.assertEqual(shell.association_subject_model, "plasticos.transaction")
        self.assertEqual(shell.association_subject_id, self.tx_a.id)
        self.assertIn(self.tx_a.name, shell.association_source_reference)
        self.assertIn(message.message_id, shell.association_source_reference)
        self.assertEqual(native.association_subject_model, "plasticos.transaction")
        self.assertEqual(native.association_subject_id, self.tx_a.id)
        # Still pending: nothing accepted, associated or verified.
        self.assertEqual(shell.association_state, "pending")
        self.assertEqual(shell.res_model, "documents.document")
        self.assertFalse(shell.transaction_id)
        self.assertFalse(shell.source_reference)
        self.assertFalse(shell.verified)
        self.assertFalse(native.verified)
        self.assertEqual(
            self.env["plasticos.document"].search_count([("association_state", "=", "accepted")]), accepted_before
        )

    def test_document_prefill_never_overwrites_a_chosen_subject(self):
        native = self._native("chosen.pdf")
        shell = native.plasticos_doc_id
        shell.write({"association_subject_model": "plasticos.transaction", "association_subject_id": self.tx_b.id})
        self._email(native, f"POD {self.tx_a.name}")
        self.assertEqual(shell.association_subject_id, self.tx_b.id)

    def test_document_email_with_conflicting_references_goes_to_the_manager(self):
        native = self._native("conflict.pdf")
        shell = native.plasticos_doc_id
        self._email(native, f"{self.tx_a.name} / {self.tx_b.name}")
        self.assertFalse(shell.association_subject_model)
        self.assertFalse(shell.association_subject_id)
        self.assertIn("conflict", shell.pending_reason)
        self.assertIn(self.tx_a.name, shell.pending_reason)
        self.assertIn(self.tx_b.name, shell.pending_reason)
        activity = self.env["mail.activity"].search(
            [("res_model", "=", "documents.document"), ("res_id", "=", native.id), ("summary", "=", SUMMARY)]
        )
        self.assertEqual(len(activity), 1)
        self.assertIn(self.tx_b.name, activity.note)
        self.assertEqual(shell.association_state, "pending")

    def test_document_email_without_a_reference_changes_nothing(self):
        native = self._native("none.pdf")
        shell = native.plasticos_doc_id
        reason = shell.pending_reason
        self._email(native, "paperwork attached", "<p>thanks</p>")
        self.assertFalse(shell.association_subject_model)
        self.assertFalse(shell.association_source_reference)
        self.assertEqual(shell.pending_reason, reason)

    def test_document_without_an_email_is_not_matched_by_file_name_alone(self):
        native = self._native(f"{self.tx_a.name}.pdf")
        self.assertFalse(native.plasticos_doc_id.association_subject_model)

    # ── B9 sender party check ────────────────────────────────
    def test_document_from_a_sender_that_is_not_a_party_is_not_prefilled(self):
        stranger = self.env["res.partner"].create({"name": "B9 Stranger", "is_company": True})
        native = self._native("stranger.pdf")
        shell = native.plasticos_doc_id
        self._email(native, f"POD {self.tx_a.name}", author=stranger)
        self.assertFalse(shell.association_subject_model)
        self.assertFalse(shell.association_subject_id)
        self.assertFalse(native.association_subject_model)
        self.assertIn(self.tx_a.name, shell.pending_reason)
        self.assertIn("B9 Stranger", shell.pending_reason)
        self.assertEqual(shell.association_state, "pending")
        activity = self.env["mail.activity"].search(
            [("res_model", "=", "documents.document"), ("res_id", "=", native.id), ("summary", "=", SUMMARY)]
        )
        self.assertEqual(len(activity), 1)
        self.assertIn("B9 Stranger", activity.note)

    def test_document_from_an_unknown_sender_is_prefilled_with_a_note(self):
        native = self._native("unknown-sender.pdf")
        shell = native.plasticos_doc_id
        self._email(native, f"POD {self.tx_a.name}", author=self.env["res.partner"])
        self.assertEqual(shell.association_subject_model, "plasticos.transaction")
        self.assertEqual(shell.association_subject_id, self.tx_a.id)
        self.assertIn("sender is unknown", shell.pending_reason)
        self.assertEqual(shell.association_state, "pending")
        self.assertFalse(shell.verified)

    def test_parties_are_the_vendor_side_and_carriers_only(self):
        parties = self.service._reference_parties(self.tx_a)
        self.assertIn(self.partner, parties)
        buyer = self.env["res.partner"].create({"name": "B9 Buyer Only", "is_company": True, "customer_rank": 1})
        sale = self.env["sale.order"].create({"partner_id": buyer.id})
        self.assertNotIn(buyer, self.service._reference_parties(sale))
        self.assertFalse(self.service._reference_parties(None))
