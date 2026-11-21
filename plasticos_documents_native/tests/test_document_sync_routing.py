"""Document-sync review routing by DEC-010, review signals by DEC-019 (TASK-060, A13-A15, A18, A33)."""

import base64

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents.models.exception_router import EXC_ASSOCIATION_REVIEW, Obligation
from odoo.tests.common import tagged

SUMMARY = "Document association needs review"
OPERATIONS_GROUP = "plasticos_security_base.group_operations_manager"
LOGISTICS_GROUP = "plasticos_security_base.group_logistics_ops"


@tagged("post_install", "-at_install", "documents", "exception_routing")
class TestDocumentSyncRouting(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        internal = cls.env.ref("base.group_user")
        cls.uploader = cls.env["res.users"].create(
            {"name": "Route Uploader", "login": "route_uploader", "group_ids": [(6, 0, [internal.id])]}
        )
        cls.ops_manager = cls.env["res.users"].create(
            {
                "name": "Route Ops Manager",
                "login": "route_native_ops",
                "group_ids": [(6, 0, [internal.id, cls.env.ref(OPERATIONS_GROUP).id])],
            }
        )
        cls.logistics_user = cls.env["res.users"].create(
            {
                "name": "Route Logistics",
                "login": "route_native_logistics",
                "group_ids": [(6, 0, [internal.id, cls.env.ref(LOGISTICS_GROUP).id])],
            }
        )
        partner = cls.env["res.partner"].create({"name": "Route Trucker", "is_company": True, "supplier_rank": 1})
        cls.tx = cls.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1}
        )
        cls.folder = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        cls.service = cls.env["plasticos.document.sync"]
        cls.router = cls.env["plasticos.exception.router"]
        cls.signals = {}
        for name in ("Needs Review", "Evidence Gap", "Duplicate Candidate", "Includes Supporting Evidence"):
            tag = cls.env["documents.tag"].search([("name", "=", name)], limit=1)
            cls.signals[name] = tag or cls.env["documents.tag"].create({"name": name})

    def _native(self, name, doc_type):
        return self.env["documents.document"].create(
            {
                "name": name,
                "folder_id": self.folder.id,
                "datas": base64.b64encode(f"%PDF-1.4 {name}".encode()),
                "owner_id": self.uploader.id,
                "doc_type": doc_type,
            }
        )

    def _attribute(self, native):
        """One resolved subject, as the reference match or a person sets it; still pending."""
        native.plasticos_doc_id.write(
            {"association_subject_model": "plasticos.transaction", "association_subject_id": self.tx.id}
        )
        self.service.sync_native_to_legacy(native)

    def _open(self, native, summary=SUMMARY):
        return self.env["mail.activity"].search(
            [("res_model", "=", "documents.document"), ("res_id", "=", native.id), ("summary", "=", summary)]
        )

    def _is_logistics_owner(self, user):
        return user.has_group(LOGISTICS_GROUP) and not user.has_group(OPERATIONS_GROUP)

    def test_unattributed_bol_review_goes_to_operations(self):
        native = self._native("route-unattributed.pdf", "bol")
        activity = self._open(native)
        self.assertEqual(len(activity), 1)
        self.assertTrue(activity.user_id.has_group(OPERATIONS_GROUP))
        self.assertEqual(
            activity.activity_type_id, self.env.ref("plasticos_documents.activity_type_association_review")
        )

    def test_attributed_bol_review_moves_to_logistics_once(self):
        native = self._native("route-attributed.pdf", "bol")
        self._attribute(native)
        self._attribute(native)
        activity = self._open(native)
        self.assertEqual(len(activity), 1)
        self.assertTrue(self._is_logistics_owner(activity.user_id))

    def test_attributed_invoice_review_stays_with_operations(self):
        native = self._native("route-invoice.pdf", "invoice")
        self._attribute(native)
        self.assertTrue(self._open(native).user_id.has_group(OPERATIONS_GROUP))

    def test_one_original_with_two_obligations_has_two_owners(self):
        """A15: one file, separately attributable obligations, each with its own owner."""
        native = self._native("route-combined.pdf", "bol")
        self._attribute(native)
        invoice_part = Obligation(
            "Invoice part needs review",
            self.router.purpose_from_doc_type("invoice", attributed=True),
            EXC_ASSOCIATION_REVIEW,
            "The combined original also carries the supplier invoice.",
        )
        for _run in range(2):
            self.router.schedule(native, invoice_part, native.company_id)
            self.service.sync_native_to_legacy(native)
        shipping = self._open(native)
        financial = self._open(native, invoice_part.summary)
        self.assertEqual(len(shipping), 1)
        self.assertEqual(len(financial), 1)
        self.assertNotEqual(shipping.user_id, financial.user_id)
        self.assertTrue(self._is_logistics_owner(shipping.user_id))
        self.assertTrue(financial.user_id.has_group(OPERATIONS_GROUP))
        self.assertEqual(
            len(self.env["plasticos.document"].search([("attachment_id", "=", native.attachment_id.id)])), 1
        )

    def test_review_signals_route_by_dec_019(self):
        """A33 router half: Needs Review and Duplicate Candidate to Operations, Evidence Gap to the family owner."""
        native = self._native("route-signals.pdf", "bol")
        native.write(
            {
                "tag_ids": [
                    (4, self.signals["Needs Review"].id),
                    (4, self.signals["Evidence Gap"].id),
                    (4, self.signals["Duplicate Candidate"].id),
                    (4, self.signals["Includes Supporting Evidence"].id),
                ]
            }
        )
        for _run in range(2):
            self.service.sync_native_to_legacy(native)
        needs_review = self._open(native, "Review signal: Needs Review")
        gap = self._open(native, "Review signal: Evidence Gap")
        duplicate = self._open(native, "Review signal: Duplicate Candidate")
        self.assertEqual(len(needs_review), 1)
        self.assertEqual(len(gap), 1)
        self.assertEqual(len(duplicate), 1)
        self.assertTrue(needs_review.user_id.has_group(OPERATIONS_GROUP))
        self.assertTrue(duplicate.user_id.has_group(OPERATIONS_GROUP))
        # An Evidence Gap on an identified shipping document is never escalated to Operations.
        self.assertTrue(self._is_logistics_owner(gap.user_id))
        self.assertFalse(self._open(native, "Review signal: Includes Supporting Evidence"))
        native.write({"tag_ids": [(3, self.signals["Evidence Gap"].id)]})
        self.service.sync_native_to_legacy(native)
        self.assertFalse(self._open(native, "Review signal: Evidence Gap"))
        self.assertEqual(self._open(native, "Review signal: Needs Review"), needs_review)

    def test_reroute_moves_uploader_reviews_once(self):
        native = self._native("route-migrate.pdf", "bol")
        activity = self._open(native)
        todo = self.env.ref("mail.mail_activity_data_todo")
        activity.write({"user_id": self.uploader.id, "activity_type_id": todo.id})
        first = self.service.reroute_open_reviews()
        self.assertGreaterEqual(first.rerouted, 1)
        self.assertTrue(activity.user_id.has_group(OPERATIONS_GROUP))
        self.assertEqual(
            activity.activity_type_id, self.env.ref("plasticos_documents.activity_type_association_review")
        )
        second = self.service.reroute_open_reviews()
        self.assertEqual(second.rerouted, 0)
