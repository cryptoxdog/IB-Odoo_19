"""B1 manager review routing, B2 hold on arrival, B3 least-privilege access."""

import base64
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents.models.exception_router import EXC_ASSOCIATION_REVIEW
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

SUMMARY = "Document association needs review"
NO_REVIEWER = "No Operations Manager is available to review this record."


@tagged("post_install", "-at_install", "documents", "integrity_controls")
class TestReviewRoutingAndHold(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: Enterprise documents.document is not installed")
        internal = cls.env.ref("base.group_user")
        cls.manager_group = cls.env.ref("plasticos_security_base.group_operations_manager")
        cls.uploader = cls.env["res.users"].create(
            {"name": "B1 Sales Uploader", "login": "b1_sales_uploader", "group_ids": [(6, 0, [internal.id])]}
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "B1 Operations Manager",
                "login": "b1_ops_manager",
                "group_ids": [(6, 0, [internal.id, cls.manager_group.id])],
            }
        )
        cls.folder = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        cls.service = cls.env["plasticos.document.sync"]

    def _native(self, name="hold.pdf", **extra):
        vals = {
            "name": name,
            "folder_id": self.folder.id,
            "datas": base64.b64encode(b"%PDF-1.4 integrity"),
            "owner_id": self.uploader.id,
        }
        vals.update(extra)
        return self.env["documents.document"].create(vals)

    def _activities(self, native):
        return self.env["mail.activity"].search(
            [("res_model", "=", "documents.document"), ("res_id", "=", native.id), ("summary", "=", SUMMARY)]
        )

    def _eligible(self):
        return self.manager_group.all_user_ids.filtered(lambda u: u.active and not u.share and u.id != 1).sorted("id")

    # ── B1 ───────────────────────────────────────────────────
    def test_review_goes_to_an_operations_manager_not_the_uploader(self):
        native = self._native(doc_type="bol")
        activity = self._activities(native)
        self.assertEqual(len(activity), 1)
        self.assertNotEqual(activity.user_id, self.uploader)
        self.assertIn(self.manager_group, activity.user_id.all_group_ids)
        self.assertEqual(activity.user_id, self._eligible()[:1])

    def test_review_without_an_owner_still_reaches_a_manager(self):
        native = self._native(doc_type="bol", owner_id=False)
        self.assertEqual(len(self._activities(native)), 1)

    def _ops_route(self):
        router = self.env["plasticos.exception.router"]
        purpose = router.purpose_from_doc_type("bol", attributed=False, attribution_reason="No reference.")
        return router, router.route(purpose, EXC_ASSOCIATION_REVIEW)

    def test_reviewer_is_deterministic_and_skips_inactive_users(self):
        router, route = self._ops_route()
        first = router.owner(route, self.env.company)
        self.assertEqual(first, router.owner(route, self.env.company))
        self.assertTrue(first.active)
        self.assertFalse(first.share)
        self.assertNotEqual(first.id, 1)
        self.assertNotEqual(first, self.env.ref("plasticos_base.user_system_cron"))
        first.active = False
        second = router.owner(route, self.env.company)
        self.assertNotEqual(second, first)
        self.assertTrue(not second or second.active)

    def test_reviewer_outside_the_company_is_not_chosen(self):
        router, route = self._ops_route()
        other = self.env["res.company"].create({"name": "B1 Other Company"})
        reviewer = router.owner(route, other)
        self.assertTrue(not reviewer or other in reviewer.company_ids)
        self.assertNotEqual(reviewer, self.manager)

    def test_cron_user_is_never_the_reviewer(self):
        cron_user = self.env.ref("plasticos_base.user_system_cron")
        cron_user.write({"group_ids": [(4, self.manager_group.id)]})
        router, route = self._ops_route()
        self.assertNotEqual(router.owner(route, self.env.company), cron_user)
        native = self._native(doc_type="bol")
        self.assertNotEqual(self._activities(native).user_id, cron_user)

    def test_no_eligible_reviewer_is_logged_and_noted_once(self):
        empty = self.env["res.users"]
        router_cls = type(self.env["plasticos.exception.router"])
        with patch.object(router_cls, "owner", lambda self, route, company=None, group=None: empty):
            with self.assertLogs("odoo.addons.plasticos_documents_native.models.document_sync", level="ERROR"):
                native = self._native(doc_type="bol")
            self.assertFalse(self._activities(native))
            with self.assertLogs("odoo.addons.plasticos_documents_native.models.document_sync", level="ERROR"):
                self.service.sync_native_to_legacy(native)
            notes = native.message_ids.filtered(lambda m: NO_REVIEWER in (m.body or ""))
            self.assertEqual(len(notes), 1)
        # A manager exists again: the next sync creates the one activity.
        self.service.sync_native_to_legacy(native)
        self.assertEqual(len(self._activities(native)), 1)

    def test_review_activity_stays_single(self):
        native = self._native(doc_type="bol")
        self.service.sync_native_to_legacy(native)
        native.write({"doc_type": "scale_ticket"})
        self.service.sync_native_to_legacy(native)
        self.assertEqual(len(self._activities(native)), 1)

    # ── B2 ───────────────────────────────────────────────────
    def test_classified_original_gets_one_pending_row_on_create(self):
        native = self._native(doc_type="bol")
        shell = native.plasticos_doc_id
        self.assertTrue(shell)
        self.assertEqual(shell.association_state, "pending")
        self.assertEqual(shell.res_model, "documents.document")
        self.assertEqual(shell.res_id, native.id)
        self.assertFalse(shell.verified)
        self.assertFalse(shell.transaction_id)
        self.assertFalse(shell.load_id)
        self.assertFalse(native.verified)
        self.assertEqual(native.verification_binding(), "unresolved")

    def test_unclassified_original_gets_no_row_until_it_is_classified(self):
        native = self._native()
        self.assertFalse(native.plasticos_doc_id)
        self.assertFalse(self._activities(native))
        native.write({"name": "renamed.pdf"})
        self.assertFalse(native.plasticos_doc_id)
        native.write({"doc_type": "invoice"})
        shell = native.plasticos_doc_id
        self.assertTrue(shell)
        self.assertEqual(shell.association_state, "pending")
        native.write({"doc_type": "bol"})
        self.assertEqual(native.plasticos_doc_id, shell)
        rows = self.env["plasticos.document"].search_count([("attachment_id", "=", native.attachment_id.id)])
        self.assertEqual(rows, 1)

    def test_classified_document_without_a_file_gets_no_row(self):
        link = self.env["documents.document"].create(
            {
                "name": "link",
                "folder_id": self.folder.id,
                "type": "url",
                "url": "https://example.com",
                "doc_type": "bol",
            }
        )
        self.assertFalse(link.plasticos_doc_id)
        self.assertFalse(self._activities(link))

    def test_hold_never_accepts_native_navigation(self):
        partner = self.env["res.partner"].create({"name": "B2 Vendor", "is_company": True, "supplier_rank": 1})
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": partner.id, "buyer_id": partner.id, "quantity": 1}
        )
        accepted_before = self.env["plasticos.document"].search_count([("association_state", "=", "accepted")])
        native = self._native(doc_type="bol", transaction_id=tx.id, partner_id=partner.id)
        shell = native.plasticos_doc_id
        self.assertEqual(shell.association_state, "pending")
        self.assertFalse(shell.transaction_id)
        self.assertEqual(
            self.env["plasticos.document"].search_count([("association_state", "=", "accepted")]), accepted_before
        )

    def test_failed_hold_keeps_the_upload_and_is_logged(self):
        def boom(self, native_doc):
            raise RuntimeError("hold failed")

        with patch.object(type(self.service), "sync_native_to_legacy", boom):
            with self.assertLogs("odoo.addons.plasticos_documents_native.models.document_native", level="ERROR"):
                native = self._native(doc_type="bol")
        self.assertTrue(native.exists())
        self.assertFalse(native.plasticos_doc_id)
        self.assertGreaterEqual(self.service.batch_sync_unlinked(), 1)
        self.assertTrue(native.plasticos_doc_id)

    def test_manifest_summary_describes_the_module(self):
        module = self.env["ir.module.module"].search([("name", "=", "plasticos_documents_native")])
        self.assertNotIn("AI auto-sort", module.summary or "")
        self.assertNotIn("email alias", module.summary or "")

    # ── B3 ───────────────────────────────────────────────────
    def test_internal_user_reads_native_tags_but_cannot_change_them(self):
        self.assertFalse(self.env.ref("plasticos_documents_native.access_documents_tag_user", raise_if_not_found=False))
        tag_model = self.env["documents.tag"].with_user(self.uploader)
        tag_model.search([], limit=1).read(["name"])
        with self.assertRaises(AccessError):
            tag_model.create({"name": "B3 internal tag"})
        tag = self.env["documents.tag"].create({"name": "B3 admin tag"})
        with self.assertRaises(AccessError):
            tag.with_user(self.uploader).write({"name": "B3 renamed"})
        with self.assertRaises(AccessError):
            tag.with_user(self.uploader).unlink()

    def test_sync_service_access_is_read_only_for_internal_users(self):
        row = self.env.ref("plasticos_documents_native.access_doc_sync_all")
        self.assertTrue(row.perm_read)
        self.assertFalse(row.perm_write or row.perm_create or row.perm_unlink)
