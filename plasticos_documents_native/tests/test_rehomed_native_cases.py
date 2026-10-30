"""Exact evidence association. Native navigation is not acceptance."""

import base64
import importlib.util
import inspect
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import tagged

from .test_native_search_parity import TestNativeSearchParity
from .test_verification_delegation import TestNativeVerificationDelegation


def _migration():
    path = get_module_path("plasticos_documents") + "/migrations/19.0.2.1.4/post-migrate.py"
    spec = importlib.util.spec_from_file_location("plasticos_documents_post_19214", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged("post_install", "-at_install", "documents", "association")
class TestExactAssociation(PlasticosTestCase):
    """DOC-A exact subject, company, partial scope, and the posting boundary."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for model in ("purchase.order", "sale.order", "stock.picking", "documents.document"):
            if model not in cls.env:
                raise AssertionError(f"BLOCKED: {model} is not installed")
        cls.vendor = cls.env["res.partner"].create({"name": "Assoc Vendor", "is_company": True, "supplier_rank": 1})
        cls.other = cls.env["res.partner"].create({"name": "Assoc Other", "is_company": True, "supplier_rank": 1})
        internal = cls.env.ref("base.group_user")
        documents = cls.env.ref("plasticos_documents.group_documents_user")
        purchase = cls.env.ref("purchase.group_purchase_user")
        stock = cls.env.ref("stock.group_stock_user")
        cls.clerk = cls.env["res.users"].create(
            {
                "name": "Evidence Clerk",
                "login": "phase_b_clerk",
                "group_ids": [(6, 0, [internal.id, documents.id, purchase.id, stock.id])],
            }
        )
        cls.internal = cls.env["res.users"].create(
            {
                "name": "Assoc Internal",
                "login": "phase_b_internal",
                "group_ids": [(6, 0, [internal.id])],
            }
        )
        cls.tag = cls.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        if not cls.tag:
            cls.tag = cls.env["plasticos.document.tag"].create({"name": "Assoc BOL", "code": "ASSOC_BOL"})
        cls.folder = cls.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        cls.company_b = cls.env["res.company"].create({"name": "Assoc Other Company"})

    def _native(self, name="evidence.pdf", **extra):
        vals = {
            "name": name,
            "folder_id": self.folder.id,
            "datas": base64.b64encode(b"%PDF-1.4 phase-b"),
            "doc_type": "bol",
            "owner_id": self.clerk.id,
        }
        vals.update(extra)
        return self.env["documents.document"].create(vals)

    def _accepted_count(self):
        return self.env["plasticos.document"].search_count([("association_state", "=", "accepted")])

    def _load(self):
        sale = self.env["sale.order"].create({"partner_id": self.vendor.id})
        return self.env["plasticos.load"].create({"sale_order_id": sale.id})

    def test_partner_recency_does_not_link_and_review_is_idempotent(self):
        older = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 1}
        )
        newest = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 2}
        )
        native = self._native(partner_id=self.vendor.id)
        self.env["documents.document"]._auto_link_partner(native)
        self.assertFalse(native.transaction_id)
        self.assertFalse(native.load_id)
        before = self._accepted_count()
        mail_before = self.env["mail.mail"].search_count([])
        self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        self.assertEqual(self._accepted_count(), before)
        self.assertFalse(
            self.env["plasticos.document"].search(
                [
                    ("res_model", "=", "plasticos.transaction"),
                    ("res_id", "in", [older.id, newest.id]),
                    ("association_state", "=", "accepted"),
                ]
            )
        )
        activities = self.env["mail.activity"].search_count(
            [
                ("res_model", "=", "documents.document"),
                ("res_id", "=", native.id),
                ("summary", "=", "Document association needs review"),
            ]
        )
        self.assertEqual(activities, 1)
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_before)
        shells = self.env["plasticos.document"].search_count(
            [("attachment_id", "=", native.attachment_id.id), ("association_state", "=", "pending")]
        )
        self.assertEqual(shells, 1)

    def test_purchase_order_association_does_not_invent_a_buyer_or_movement(self):
        purchase = self.env["purchase.order"].create({"partner_id": self.vendor.id, "partner_ref": "PO-EXACT"})
        orders = self.env["sale.order"].search_count([])
        transactions = self.env["plasticos.transaction"].search_count([])
        loads = self.env["plasticos.load"].search_count([])
        native = self._native("supplier.pdf", partner_id=self.vendor.id)
        row = native.with_user(self.clerk).action_associate_exact(
            "purchase.order",
            purchase.id,
            source_reference="request 9",
        )
        self.assertEqual(row.res_model, "purchase.order")
        self.assertEqual(row.res_id, purchase.id)
        self.assertEqual(row.association_state, "accepted")
        self.assertEqual(row.associated_by, self.clerk)
        self.assertTrue(row.source_revision)
        self.assertFalse(row.verified)
        self.assertFalse(row.transaction_id)
        self.assertFalse(row.load_id)
        self.assertEqual(self.env["sale.order"].search_count([]), orders)
        self.assertEqual(self.env["plasticos.transaction"].search_count([]), transactions)
        self.assertEqual(self.env["plasticos.load"].search_count([]), loads)
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        self.assertTrue(warehouse)
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.vendor.id,
                "picking_type_id": warehouse.in_type_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": warehouse.lot_stock_id.id,
            }
        )
        state = picking.state
        second = native.with_user(self.clerk).action_associate_exact(
            "stock.picking",
            picking.id,
            source_reference="receipt exists",
        )
        self.assertNotEqual(second, row)
        self.assertEqual(second.attachment_id, row.attachment_id)
        self.assertEqual(second.res_model, "stock.picking")
        self.assertFalse(second.verified)
        self.assertFalse(row.verified)
        self.assertEqual(picking.state, state)
        self.assertEqual(
            self.env["ir.attachment"].search_count([("id", "=", native.attachment_id.id)]),
            1,
        )

    def test_one_original_two_loads_do_not_share_verification_or_quantity(self):
        native = self._native("shared.pdf")
        load_a = self._load()
        load_b = self._load()
        state_a = load_a.state
        state_b = load_b.state
        first = native.with_user(self.clerk).action_associate_exact(
            "plasticos.load",
            load_a.id,
            source_reference="load a",
            covered_quantity=20000,
        )
        second = native.with_user(self.clerk).action_associate_exact(
            "plasticos.load",
            load_b.id,
            source_reference="load b",
        )
        first.with_user(self.clerk).action_verify()
        self.assertTrue(first.verified)
        self.assertFalse(second.verified)
        self.assertEqual(first.covered_quantity, 20000)
        self.assertEqual(first.attachment_id, second.attachment_id)
        self.assertEqual(load_a.state, state_a)
        self.assertEqual(load_b.state, state_b)
        native.invalidate_recordset()
        self.assertFalse(native.verified)

    def test_same_reference_in_another_company_is_refused(self):
        purchase_a = self.env["purchase.order"].create({"partner_id": self.vendor.id, "partner_ref": "PO-SHARED"})
        purchase_b = (
            self.env["purchase.order"]
            .with_company(self.company_b)
            .create(
                {
                    "partner_id": self.vendor.id,
                    "company_id": self.company_b.id,
                    "partner_ref": "PO-SHARED",
                }
            )
        )
        self.assertEqual(
            self.env["purchase.order"].search_count([("partner_ref", "=", "PO-SHARED")]),
            2,
        )
        visible = self.env["purchase.order"].with_user(self.clerk).search_count([("partner_ref", "=", "PO-SHARED")])
        self.assertEqual(visible, 1)
        native = self._native("cross.pdf", partner_id=self.vendor.id)
        attachments = self.env["ir.attachment"].search_count([])
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            native.with_user(self.clerk).action_associate_exact(
                "purchase.order",
                purchase_b.id,
                source_reference="PO-SHARED",
            )
        self.assertFalse(
            self.env["plasticos.document"].search(
                [("res_model", "=", "purchase.order"), ("res_id", "=", purchase_b.id)]
            )
        )
        self.assertEqual(self.env["ir.attachment"].search_count([]), attachments)
        accepted = native.with_user(self.clerk).action_associate_exact(
            "purchase.order",
            purchase_a.id,
            source_reference="PO-SHARED company A",
        )
        self.assertEqual(accepted.subject_company_id, purchase_a.company_id)
        self.assertNotEqual(accepted.subject_company_id, purchase_b.company_id)

    def test_mismatched_party_stale_revision_and_direct_write_are_refused(self):
        purchase = self.env["purchase.order"].create({"partner_id": self.vendor.id})
        native = self._native("mismatch.pdf", partner_id=self.other.id)
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            native.with_user(self.clerk).action_associate_exact(
                "purchase.order",
                purchase.id,
                source_reference="wrong party",
            )
        native.partner_id = self.vendor
        self.env["plasticos.document.sync"].sync_native_to_legacy(native)
        shell = native.plasticos_doc_id
        shell.candidate_partner_id = self.vendor
        row = shell.with_user(self.clerk).action_associate(
            "purchase.order",
            purchase.id,
            source_reference="vendor confirmed",
        )
        row.with_user(self.clerk).action_verify()
        stamp = row.verified_at
        row.attachment_id.write({"datas": base64.b64encode(b"%PDF-1.4 replaced")})
        self.assertTrue(row.verified)
        self.assertEqual(row.verified_at, stamp)
        self.assertEqual(row.association_state, "accepted")
        self.assertTrue(row.association_review_required)
        self.assertFalse(row._currently_eligible())
        with self.assertRaises(AccessError):
            row.with_user(self.clerk).write({"res_model": "plasticos.transaction", "res_id": 1})
        with self.assertRaises(AccessError):
            row.with_user(self.clerk).write({"associated_by": False, "association_state": "pending"})
        self.assertEqual(row.res_model, "purchase.order")
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            row.with_user(self.clerk).action_verify()
        with self.assertRaises(AccessError):
            shell.with_user(self.clerk).write(
                {
                    "res_model": "plasticos.transaction",
                    "res_id": 1,
                    "association_state": "accepted",
                }
            )
        with self.assertRaises(UserError):
            self._native("blank.pdf").with_user(self.clerk).action_associate_exact(
                "purchase.order",
                purchase.id,
                source_reference="  ",
            )

    def test_one_load_does_not_clear_the_shipment_or_post(self):
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 44000}
        )
        loads = self._load() | self._load() | self._load()
        self.env["plasticos.document.rule"].create(
            {
                "name": "phase-b transaction bol",
                "tag_id": self.tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": True,
                "required_for_close": True,
            }
        )
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.vendor.id,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Buyer", "quantity": 1, "price_unit": 10.0})],
            }
        )
        tx.customer_invoice_id = invoice
        native = self._native("partial.pdf")
        states = {load.id: load.state for load in loads}
        row = native.with_user(self.clerk).action_associate_exact(
            "plasticos.load",
            loads[0].id,
            source_reference="scale ticket 20000",
            covered_quantity=20000,
        )
        mail_before = self.env["mail.mail"].search_count([])
        with (
            patch.object(type(tx), "_auto_post_pending_invoices", side_effect=AssertionError("autopost")),
            patch.object(type(invoice), "action_post", side_effect=AssertionError("post")),
            patch.object(type(loads), "action_dispatch", side_effect=AssertionError("dispatch")),
        ):
            row.with_user(self.clerk).action_verify()
            tx.invalidate_recordset()
            tx._compute_compliance()
        self.assertEqual(row.covered_quantity, 20000)
        self.assertEqual(tx.quantity, 44000)
        self.assertEqual(tx.compliance_status, "missing")
        self.assertFalse(
            self.env["plasticos.document"].search(
                [
                    ("res_model", "=", "plasticos.load"),
                    ("res_id", "in", loads[1:].ids),
                    ("association_state", "=", "accepted"),
                ]
            )
        )
        self.assertEqual({load.id: load.state for load in loads}, states)
        self.assertEqual(invoice.state, "draft")
        self.assertEqual(self.env["mail.mail"].search_count([]), mail_before)

    def test_native_navigation_and_blank_link_resolution_do_not_accept(self):
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 1}
        )
        load = self.env["plasticos.load"].create({})
        native = self._native("nav.pdf", partner_id=self.vendor.id, transaction_id=tx.id, load_id=load.id)
        service = self.env["plasticos.document.sync"]
        self.assertEqual(service._resolve_business_link(native), ("documents.document", native.id))
        legacy = service.sync_native_to_legacy(native)
        self.assertEqual(legacy.res_model, "documents.document")
        self.assertFalse(legacy.transaction_id)
        self.assertFalse(legacy.load_id)
        self.assertEqual(legacy.association_state, "pending")
        self.assertIn("disagree", legacy.pending_reason)
        other = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 3}
        )
        native.write({"transaction_id": other.id})
        again = service.sync_native_to_legacy(native)
        self.assertEqual(again, legacy)
        self.assertFalse(legacy.transaction_id)
        self.assertEqual(legacy.association_state, "pending")
        with self.assertRaises(AccessError):
            legacy.with_user(self.internal).action_associate(
                "plasticos.transaction",
                tx.id,
                source_reference="internal",
            )

    def test_repeat_form_command_and_upgrade_do_not_duplicate_or_reverify(self):
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 5}
        )
        native = self._native("form.pdf")
        native.write(
            {
                "association_subject_model": "plasticos.transaction",
                "association_subject_id": tx.id,
                "association_source_reference": "on screen",
            }
        )
        row = native.with_user(self.clerk).action_associate_from_form()
        again = native.with_user(self.clerk).action_associate_from_form()
        self.assertEqual(again, row)
        self.assertFalse(row.verified)
        self.assertEqual(row.associated_by, self.clerk)
        self.assertEqual(
            self.env["plasticos.document"].search_count(
                [
                    ("attachment_id", "=", native.attachment_id.id),
                    ("association_state", "=", "accepted"),
                ]
            ),
            1,
        )
        row.with_user(self.clerk).action_verify()
        verified_at = row.verified_at
        self.env.cr.execute(
            """
            UPDATE plasticos_document
               SET association_state = 'pending',
                   associated_by = NULL
             WHERE id = %s
            """,
            (row.id,),
        )
        migrate = _migration()
        migrate(self.env.cr, "19.0.2.1.3")
        migrate(self.env.cr, "19.0.2.1.3")
        row.invalidate_recordset()
        self.assertEqual(row.association_state, "accepted")
        self.assertEqual(row.verified_at, verified_at)
        self.assertTrue(row.verified)

    def test_projected_verification_search_stays_on_the_exact_row(self):
        from odoo.addons.plasticos_documents_native.models.document_native import DocumentNative

        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "quantity": 1000}
        )
        native = self._native("search.pdf")
        pending = self._native("pending-search.pdf")
        row = native.with_user(self.clerk).action_associate_exact(
            "plasticos.transaction", tx.id, source_reference="desk"
        )
        row.with_user(self.clerk).action_verify()
        native.invalidate_recordset()
        self.assertEqual(row.res_model, "plasticos.transaction")
        self.assertTrue(row.verified)
        self.assertEqual(
            self.env["plasticos.document"].search_count([("attachment_id", "=", native.attachment_id.id)]),
            1,
        )
        self.assertEqual(native.plasticos_doc_id, row)
        self.assertEqual(native.verification_binding(), "exact")
        self.assertTrue(native.verified)
        rows = native._exact_projected_rows([("verified", "=", True)])
        self.assertIn(row, rows)
        documents = self.env["documents.document"]
        pair = [("id", "in", [native.id, pending.id])]
        self.assertEqual(documents.search([("verified", "=", True), *pair]), native)
        self.assertEqual(documents.search([("verified_by", "=", self.clerk.id), *pair]), native)
        self.assertEqual(documents.search([("verified", "=", False), *pair]), pending)
        self.assertEqual(documents.search([("verified_by", "=", False), *pair]), pending)
        self.assertEqual(documents.search([("verified_by", "!=", False), *pair]), native)
        self.assertNotIn(native, documents.search([("verified_by", "!=", self.clerk.id), *pair]))
        self.assertIn(pending, documents.search([("verified_by", "!=", self.clerk.id), *pair]))

        shared = self._native("shared-search.pdf")
        load_a = self._load()
        load_b = self._load()
        shared.with_user(self.clerk).action_associate_exact("plasticos.load", load_a.id, source_reference="a")
        shared.with_user(self.clerk).action_associate_exact("plasticos.load", load_b.id, source_reference="b")
        shared.invalidate_recordset()
        self.assertFalse(shared.verified)
        self.assertFalse(documents.search([("verified", "=", True), ("id", "=", shared.id)]))

        source = inspect.getsource(DocumentNative._search_projected_boolean)
        source += inspect.getsource(DocumentNative._search_verified_by)
        self.assertNotIn('self.search([("type", "=", "binary")])', source)

    def test_each_load_document_recomputes_only_its_parent(self):
        order = self.env["sale.order"].create({"partner_id": self.vendor.id})
        parent = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "sale_order_id": order.id}
        )
        other_order = self.env["sale.order"].create({"partner_id": self.vendor.id})
        other = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "sale_order_id": other_order.id}
        )
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        sibling = self.env["plasticos.load"].create({"sale_order_id": other_order.id, "transaction_id": other.id})
        self.assertEqual(load.transaction_id, parent)
        attachment = self.env["ir.attachment"].create(
            {
                "name": "load-parent.txt",
                "datas": base64.b64encode(b"load-parent"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        document = self.env["plasticos.document"].create(
            {
                "name": "Load parent",
                "tag_id": self.tag.id,
                "res_model": "plasticos.load",
                "res_id": load.id,
                "load_id": load.id,
                "attachment_id": attachment.id,
            }
        )
        found = document._get_related_transactions(document)
        self.assertEqual(found, parent)
        self.assertNotIn(other, found)
        self.assertNotIn(sibling.transaction_id, document._get_related_transactions(document))

    def test_sibling_scale_ticket_does_not_finish_the_other_load(self):
        from odoo.addons.plasticos_logistics.models.load import (
            _FREIGHT_INTERNAL_WRITE,
            _FREIGHT_INTERNAL_WRITE_TOKEN,
        )

        tag = self.env["plasticos.document.tag"].search([("code", "=", "SCALE")], limit=1)
        if not tag:
            tag = self.env["plasticos.document.tag"].create({"name": "Scale Ticket", "code": "SCALE"})
        order = self.env["sale.order"].create({"partner_id": self.vendor.id})
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.vendor.id, "buyer_id": self.vendor.id, "sale_order_id": order.id}
        )
        load_a = self.env["plasticos.load"].create({"sale_order_id": order.id, "transaction_id": tx.id})
        load_b = self.env["plasticos.load"].create({"sale_order_id": order.id, "transaction_id": tx.id})
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        when = fields.Datetime.now() - timedelta(days=5)
        pickup = fields.Datetime.now() - timedelta(days=3)
        (load_a | load_b).with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"state": "delivered", "delivered_at": when, "dispatched_at": pickup}
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "scale-a.txt",
                "datas": base64.b64encode(b"scale-a"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        self.env["plasticos.document"].create(
            {
                "name": "Scale A",
                "tag_id": tag.id,
                "res_model": "plasticos.load",
                "res_id": load_a.id,
                "load_id": load_a.id,
                "attachment_id": attachment.id,
            }
        )

        def eligible(document):
            return document.load_id == load_a

        with patch.object(type(self.env["plasticos.document"]), "_currently_eligible", eligible):
            self.assertTrue(tx._load_has_current_scale_ticket(load_a, tag))
            self.assertFalse(tx._load_has_current_scale_ticket(load_b, tag))
            self.env["ir.config_parameter"].set_param(
                "plasticos_documents.scale_ticket_scan_cursor", str(load_a.id - 1)
            )
            tx.cron_check_scale_tickets()
            self.assertFalse(load_a.scale_ticket_reminder_sent)
            self.assertTrue(load_b.scale_ticket_reminder_sent)
            self.assertTrue(any(load_b.name in (message.body or "") for message in load_b.message_ids))
            noted = len(load_b.message_ids)
            self.env["ir.config_parameter"].set_param(
                "plasticos_documents.scale_ticket_scan_cursor", str(load_a.id - 1)
            )
            tx.cron_check_scale_tickets()
            self.assertEqual(len(load_b.message_ids), noted)


class TestNativeVerificationOnEnterpriseFixture(TestNativeVerificationDelegation):
    """Same cases, discovered from the native addon that owns the import."""

    allow_inherited_tests_method = True


class TestPr322NativeSearch(TestNativeSearchParity):
    """Run the native search truth table from the native addon."""

    allow_inherited_tests_method = True
