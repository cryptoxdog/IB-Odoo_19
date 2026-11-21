"""AC-070 / A23-A25 / A33: native classification reaches the business-evidence bridge (TASK-070, N-012).

Auto-Sort writes only ``folder_id`` and ``tag_ids``. Before TASK-070 a document that got exactly
one type tag kept ``doc_type`` empty and never reached ``plasticos.document.sync``.
"""

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged

OPERATIONS_GROUP = "plasticos_security_base.group_operations_manager"
LOGISTICS_GROUP = "plasticos_security_base.group_logistics_ops"
NATIVE = "plasticos_documents_native"


@tagged("post_install", "-at_install", "documents", "exception_routing")
class TestClassificationBridge(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        internal = cls.env.ref("base.group_user")
        for login, group in (("bridge_ops", OPERATIONS_GROUP), ("bridge_logistics", LOGISTICS_GROUP)):
            cls.env["res.users"].create(
                {"name": login, "login": login, "group_ids": [(6, 0, [internal.id, cls.env.ref(group).id])]}
            )
        cls.inbox = cls.env.ref(f"{NATIVE}.folder_plasticos_inbox")
        cls.bols = cls.env.ref(f"{NATIVE}.folder_plasticos_bols")
        cls.orders = cls.env.ref(f"{NATIVE}.folder_plasticos_customer_orders")
        cls.tag = {
            name: cls.env.ref(f"{NATIVE}.{name}")
            for name in (
                "tag_bol",
                "tag_packing_list",
                "tag_receiving_report",
                "tag_scale_ticket",
                "tag_needs_review",
                "tag_verified",
                "tag_evidence_gap",
                "tag_includes_supporting_evidence",
                "tag_vendor_bill",
            )
        }

    def _upload(self, name, folder=None):
        return self.env["documents.document"].create(
            {
                "name": name,
                "folder_id": (folder or self.inbox).id,
                "datas": base64.b64encode(f"%PDF-1.4 {name}".encode()),
            }
        )

    def _add_tags(self, document, *names):
        # The shape Enterprise's add-tags tool writes: ``self.tag_ids |= tags``.
        document.tag_ids |= (
            self.env["documents.document"].browse().env["documents.tag"].browse([self.tag[name].id for name in names])
        )

    def _activities(self, document, summary):
        return self.env["mail.activity"].search(
            [("res_model", "=", "documents.document"), ("res_id", "=", document.id), ("summary", "=", summary)]
        )

    # ── A23: one type tag reaches the bridge ────────────────────
    def test_one_type_tag_sets_doc_type_and_syncs_once(self):
        document = self._upload("bridge-one-tag.pdf")
        self.assertFalse(document.doc_type)
        self._add_tags(document, "tag_bol")
        self.assertEqual(document.doc_type, "bol")
        self.assertEqual(document.doc_type_source, "tag")
        self.assertTrue(document.plasticos_doc_id)
        self.assertEqual(document.plasticos_doc_id.tag_id.code, "BOL")
        self._add_tags(document, "tag_evidence_gap")
        self.assertEqual(
            self.env["plasticos.document"].search_count([("attachment_id", "=", document.attachment_id.id)]), 1
        )

    def test_new_dec014_type_tag_maps_to_its_doc_type(self):
        document = self._upload("bridge-packing.pdf")
        self._add_tags(document, "tag_packing_list")
        self.assertEqual(document.doc_type, "packing_list")
        self.assertEqual(document.plasticos_doc_id.tag_id.code, "PACKING")

    def test_review_signal_alone_sets_no_doc_type(self):
        document = self._upload("bridge-signal.pdf")
        self._add_tags(document, "tag_includes_supporting_evidence")
        self.assertFalse(document.doc_type)
        self.assertFalse(document.plasticos_doc_id)

    # ── A24: conflicting type tags ──────────────────────────────
    def test_two_type_tags_add_needs_review_and_no_doc_type(self):
        document = self._upload("bridge-conflict.pdf")
        self._add_tags(document, "tag_bol", "tag_packing_list")
        self.assertFalse(document.doc_type)
        self.assertIn(self.tag["tag_needs_review"], document.tag_ids)
        review = self._activities(document, "Review signal: Needs Review")
        self.assertEqual(len(review), 1)
        self.assertTrue(review.user_id.has_group(OPERATIONS_GROUP))

    def test_needs_review_on_inbox_document_routes_one_operations_activity(self):
        document = self._upload("bridge-unknown.pdf")
        self._add_tags(document, "tag_needs_review")
        self._add_tags(document, "tag_needs_review")
        review = self._activities(document, "Review signal: Needs Review")
        self.assertEqual(len(review), 1)
        self.assertTrue(review.user_id.has_group(OPERATIONS_GROUP))

    def test_evidence_gap_on_a_bol_goes_to_logistics_not_operations(self):
        document = self._upload("bridge-gap.pdf")
        self._add_tags(document, "tag_bol", "tag_evidence_gap")
        gap = self._activities(document, "Review signal: Evidence Gap")
        self.assertEqual(len(gap), 1)
        self.assertTrue(gap.user_id.has_group(LOGISTICS_GROUP))
        self.assertFalse(gap.user_id.has_group(OPERATIONS_GROUP))
        self.assertFalse(self._activities(document, "Review signal: Includes Supporting Evidence"))

    # ── A25: human precedence and reasoned correction ───────────
    def test_human_doc_type_is_never_overwritten_by_a_tag(self):
        document = self._upload("bridge-human.pdf")
        document.doc_type = "receiving_report"
        self.assertEqual(document.doc_type_source, "human")
        self._add_tags(document, "tag_bol")
        self.assertEqual(document.doc_type, "receiving_report")
        self.assertEqual(document.doc_type_source, "human")

    def test_correct_classification_requires_a_reason(self):
        document = self._upload("bridge-correct-noreason.pdf")
        self._add_tags(document, "tag_bol")
        wizard = self.env["plasticos.document.classification.correction"].create(
            {"document_id": document.id, "doc_type": "packing_list", "folder_id": self.orders.id, "reason": " "}
        )
        with self.assertRaises(UserError):
            wizard.action_apply()
        self.assertEqual(document.doc_type, "bol")

    def test_correct_classification_records_reason_keeps_file_resyncs_and_survives_tags(self):
        document = self._upload("bridge-correct.pdf")
        self._add_tags(document, "tag_bol")
        original_attachment = document.attachment_id
        original_checksum = original_attachment.checksum
        shell = document.plasticos_doc_id
        self.env["plasticos.document.classification.correction"].create(
            {
                "document_id": document.id,
                "doc_type": "packing_list",
                "folder_id": self.orders.id,
                "reason": "Synthetic: itemized bales, no consignee contract terms.",
            }
        ).action_apply()

        self.assertEqual((document.doc_type, document.doc_type_source), ("packing_list", "human"))
        self.assertEqual(document.folder_id, self.orders)
        self.assertEqual(document.attachment_id, original_attachment)
        self.assertEqual(document.attachment_id.checksum, original_checksum)
        self.assertEqual(document.plasticos_doc_id, shell)
        self.assertEqual(shell.tag_id.code, "PACKING")
        subtype = self.env.ref(f"{NATIVE}.mt_classification_correction")
        reasons = document.message_ids.filtered(lambda m: m.subtype_id == subtype)
        self.assertEqual(len(reasons), 1)
        self.assertIn("itemized bales", reasons.body)

        self._add_tags(document, "tag_scale_ticket")
        self.assertEqual(document.doc_type, "packing_list")

    # ── A33: Verified only through verification ────────────────
    def test_verified_tag_is_dropped_outside_verification(self):
        document = self._upload("bridge-verified.pdf")
        self._add_tags(document, "tag_bol", "tag_verified")
        self.assertNotIn(self.tag["tag_verified"], document.tag_ids)
        document.write({"tag_ids": [(4, self.tag["tag_verified"].id)]})
        self.assertNotIn(self.tag["tag_verified"], document.tag_ids)
        created = self.env["documents.document"].create(
            {
                "name": "bridge-verified-create.pdf",
                "folder_id": self.inbox.id,
                "datas": base64.b64encode(b"%PDF-1.4 verified"),
                "tag_ids": [(6, 0, [self.tag["tag_verified"].id])],
            }
        )
        self.assertFalse(created.tag_ids)
