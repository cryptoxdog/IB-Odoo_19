"""Native verified search matches computed False for URL and shortcut rows."""

import base64
import inspect

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "documents_native", "pr322")
class TestNativeSearchParity(PlasticosTestCase):
    """Negative verification search includes every computed-false native type."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "documents.document" not in cls.env:
            raise AssertionError("BLOCKED: documents.document is not installed")
        internal = cls.env.ref("base.group_user")
        documents = cls.env.ref("plasticos_documents.group_documents_user")
        purchase = cls.env.ref("purchase.group_purchase_user")
        cls.clerk = cls.env["res.users"].create(
            {
                "name": "Search Clerk",
                "login": "pr322_search_clerk",
                "group_ids": [(6, 0, [internal.id, documents.id, purchase.id])],
            }
        )
        cls.vendor = cls.env["res.partner"].create({"name": "Search Vendor", "is_company": True, "supplier_rank": 1})
        cls.folder = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")

    def _binary(self, name):
        return self.env["documents.document"].create(
            {
                "name": name,
                "folder_id": self.folder.id,
                "datas": base64.b64encode(b"%PDF-1.4 search"),
                "doc_type": "bol",
                "owner_id": self.clerk.id,
            }
        )

    def test_url_and_shortcut_follow_computed_false_for_every_negative_operator(self):
        binary = self._binary("file.pdf")
        url = self.env["documents.document"].create(
            {
                "name": "link",
                "folder_id": self.folder.id,
                "type": "url",
                "url": "https://example.com/evidence",
                "owner_id": self.clerk.id,
            }
        )
        shortcut = binary.action_create_shortcut()
        purchase = self.env["purchase.order"].create({"partner_id": self.vendor.id, "partner_ref": "PO-SEARCH"})
        verified = self._binary("verified.pdf")
        row = verified.with_user(self.clerk).action_associate_exact(
            "purchase.order", purchase.id, source_reference="search-positive"
        )
        row.with_user(self.clerk).action_verify()
        verified.invalidate_recordset()
        self.assertFalse(url.verified)
        self.assertFalse(url.verified_by)
        self.assertFalse(shortcut.verified)
        self.assertFalse(shortcut.verified_by)
        self.assertTrue(verified.verified)
        documents = self.env["documents.document"]
        scope = [("id", "in", [url.id, shortcut.id, verified.id, binary.id])]
        negatives = url | shortcut | binary
        for domain in (
            [("verified", "=", False)],
            [("verified", "in", [False])],
            [("verified", "!=", True)],
            [("verified_by", "=", False)],
            [("verified_by", "in", [False])],
        ):
            found = documents.search([*domain, *scope])
            self.assertEqual(found, negatives, domain)
            self.assertNotIn(verified, found)
        self.assertEqual(documents.search([("verified", "=", True), *scope]), verified)
        self.assertEqual(documents.search([("verified_by", "!=", False), *scope]), verified)
        native_model = type(documents)
        source = inspect.getsource(native_model._negative_projection_domain)
        source += inspect.getsource(native_model._search_projected_boolean)
        self.assertNotIn('self.search([("type", "=", "binary")])', source)

    def test_two_accepted_scopes_stay_unverified_on_the_native_original(self):
        shared = self._binary("shared-search.pdf")
        sale_a = self.env["sale.order"].create({"partner_id": self.vendor.id})
        sale_b = self.env["sale.order"].create({"partner_id": self.vendor.id})
        load_a = self.env["plasticos.load"].create({"sale_order_id": sale_a.id})
        load_b = self.env["plasticos.load"].create({"sale_order_id": sale_b.id})
        shared.with_user(self.clerk).action_associate_exact("plasticos.load", load_a.id, source_reference="scope-a")
        shared.with_user(self.clerk).action_associate_exact("plasticos.load", load_b.id, source_reference="scope-b")
        shared.invalidate_recordset()
        self.assertFalse(shared.verified)
        documents = self.env["documents.document"]
        self.assertFalse(documents.search([("verified", "=", True), ("id", "=", shared.id)]))
        self.assertEqual(documents.search([("verified", "=", False), ("id", "=", shared.id)]), shared)
        self.assertEqual(documents.search([("verified_by", "=", False), ("id", "=", shared.id)]), shared)

    # ── Export campaign S3: operation scope (RP-05-E031) ──────────────

    def _operation_scope(self, shell, load, revision):
        return shell.with_user(self.clerk)._associate_scope(
            "plasticos.load",
            load.id,
            "booking mail",
            obligation_kind="export_gate_receipt",
            operation_revision_key=revision,
            coverage_key="container-1",
        )

    def test_operation_rows_never_satisfy_native_verified_search(self):
        """V08/V09/V12: computation and positive/negative search agree for operation rows."""
        self.patch(
            type(self.env["plasticos.document"]),
            "_scoped_obligation_kinds",
            lambda model: frozenset({"export_gate_receipt"}),
        )
        sale = self.env["sale.order"].create({"partner_id": self.vendor.id})
        load = self.env["plasticos.load"].create({"sale_order_id": sale.id})
        sync = self.env["plasticos.document.sync"]
        sole = self._binary("operation-sole.pdf")
        sole_row = self._operation_scope(sync.sync_native_to_legacy(sole), load, "BKG-1/r1")
        sole_row.with_user(self.clerk).action_verify()
        mixed = self._binary("operation-mixed.pdf")
        sync.sync_native_to_legacy(mixed)
        purchase = self.env["purchase.order"].create({"partner_id": self.vendor.id, "partner_ref": "PO-MIXED"})
        legacy = mixed.with_user(self.clerk).action_associate_exact(
            "purchase.order", purchase.id, source_reference="mixed-legacy"
        )
        legacy.with_user(self.clerk).action_verify()
        self._operation_scope(legacy, load, "BKG-2/r1").with_user(self.clerk).action_verify()
        (sole | mixed).invalidate_recordset()
        self.assertFalse(sole.verified)
        self.assertFalse(mixed.verified)
        documents = self.env["documents.document"]
        scope = [("id", "in", [sole.id, mixed.id])]
        self.assertFalse(documents.search([("verified", "=", True), *scope]))
        self.assertFalse(documents.search([("verified_by", "!=", False), *scope]))
        self.assertEqual(documents.search([("verified", "=", False), *scope]), sole | mixed)
        self.assertEqual(documents.search([("verified_by", "=", False), *scope]), sole | mixed)
