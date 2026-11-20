"""GMP-NC-B: the dashboard payout lookup honours the rep payout record rule.

Every group that can read the sales dashboard can already read payouts, so the
lookup needs no elevation. Runs under ``odoo --test-enable --test-tags /plasticos_commission``.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


def _native_documents():
    """Helpers owned by plasticos_documents_native. Loaded inside the test, not as a module dependency."""
    import importlib

    helper = importlib.import_module("odoo.addons.plasticos_documents_native.tests.test_native_projection")
    return helper.create_native_document, helper.native_model_installed, helper.native_model_name


@tagged("post_install", "-at_install")
class TestSalesDashboardPayoutAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        rep_group = cls.env.ref("plasticos_security_base.group_sales_rep")
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.rep_a = Users.create(
            {"name": "Payout Rep A", "login": "nc_b_payout_rep_a", "group_ids": [Command.set([rep_group.id])]}
        )
        cls.rep_b = Users.create(
            {"name": "Payout Rep B", "login": "nc_b_payout_rep_b", "group_ids": [Command.set([rep_group.id])]}
        )
        Tx = cls.env["plasticos.transaction"]
        cls.tx_foreign_payout = Tx.create({"user_id": cls.rep_a.id})
        cls.tx_own_payout = Tx.create({"user_id": cls.rep_a.id})
        Payout = cls.env["plasticos.commission.payout"]
        today = fields.Date.today()
        cls.payout_b = Payout.create(
            {
                "sales_rep_id": cls.rep_b.id,
                "period_start": today,
                "period_end": today,
                "transaction_ids": [Command.set(cls.tx_foreign_payout.ids)],
            }
        )
        cls.payout_a = Payout.create(
            {
                "sales_rep_id": cls.rep_a.id,
                "period_start": today,
                "period_end": today,
                "transaction_ids": [Command.set(cls.tx_own_payout.ids)],
            }
        )
        cls.env.flush_all()

    def _row(self, tx):
        return self.env["plasticos.sales.dashboard"].with_user(self.rep_a).browse(tx.id)

    def test_rep_does_not_learn_another_reps_payout(self):
        action = self._row(self.tx_foreign_payout).action_view_payout()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertNotIn(str(self.payout_b.id), str(action))

    def test_rep_still_opens_own_payout(self):
        action = self._row(self.tx_own_payout).action_view_payout()
        self.assertEqual(action["res_model"], "plasticos.commission.payout")
        self.assertEqual(action["domain"], [("id", "in", self.payout_a.ids)])


@tagged("post_install", "-at_install")
class TestSalesDashboardDocumentChecklist(TransactionCase):
    """Export campaign S3 (RP-05-E026/E027, B2, B7): checklist reads current legacy business rows.

    Transaction grain: one dashboard row per transaction, whatever its load count.
    An operation-scoped row never clears a legacy item. The native per-original
    projection is used only when PlasticOS Documents rows are unavailable.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _create_native_document, native_model_installed, native_model_name = _native_documents()
        if "plasticos.document" not in cls.env or not native_model_installed(cls.env):
            raise AssertionError("BLOCKED: PlasticOS Documents and Enterprise Documents must be installed")
        cls._create_native_document = staticmethod(_create_native_document)
        cls._native_model_name = staticmethod(native_model_name)
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.supplier = cls.env["res.partner"].create({"name": "Checklist Supplier", "supplier_rank": 1})
        cls.buyer = cls.env["res.partner"].create({"name": "Checklist Buyer", "customer_rank": 1})
        cls.verifier = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Checklist Verifier",
                    "login": "s3_checklist_verifier",
                    "group_ids": [
                        Command.set(
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref("plasticos_documents.group_documents_user").id,
                            ]
                        )
                    ],
                }
            )
        )
        Tag = cls.env["plasticos.document.tag"]
        cls.tags = {code: Tag.search([("code", "=", code)], limit=1) for code in ("BOL", "SCALE", "INV", "CO")}
        if not all(cls.tags.values()):
            raise AssertionError("BLOCKED: checklist tags are not installed")

    def setUp(self):
        super().setUp()
        self.patch(
            type(self.env["plasticos.document"]),
            "_scoped_obligation_kinds",
            lambda model: frozenset({"export_gate_receipt"}),
        )

    def _trade(self, loads=1):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {"supplier_id": self.supplier.id, "buyer_id": self.buyer.id, "sale_order_id": order.id}
        )
        created = self.env["plasticos.load"]
        for _index in range(loads):
            created |= self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(created.transaction_id, tx)
        return tx, created

    def _row(self, code, subject, verify=True, scope=None):
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{code}.pdf",
                "datas": base64.b64encode(f"checklist-{code}-{subject._name}-{subject.id}-{scope}".encode()),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )
        shell = self.env["plasticos.document"].create(
            {
                "name": code,
                "tag_id": self.tags[code].id,
                "res_model": self._native_model_name(),
                "res_id": 0,
                "attachment_id": attachment.id,
            }
        )
        if scope:
            row = shell.with_user(self.verifier)._associate_scope(
                subject._name,
                subject.id,
                "booking mail",
                obligation_kind="export_gate_receipt",
                operation_revision_key=scope,
                coverage_key="container-1",
            )
        else:
            row = shell.with_user(self.verifier).action_associate(subject._name, subject.id, f"{code} source")
        if verify:
            row.with_user(self.verifier).action_verify()
        return row

    def _dashboard(self, tx):
        self.env.flush_all()
        rows = self.env["plasticos.sales.dashboard"].search([("transaction_id", "=", tx.id)])
        self.assertEqual(len(rows), 1, "one dashboard row per transaction")
        rows.invalidate_recordset()
        return rows

    def test_business_rows_drive_the_checklist_through_loads(self):
        tx, loads = self._trade(loads=2)
        self._row("BOL", loads[0])
        self._row("SCALE", tx, verify=False)
        row = self._dashboard(tx)
        self.assertEqual(row.load_count, 2)
        self.assertEqual(row.doc_bol, "ok")
        self.assertEqual(row.doc_scale_ticket, "pending")
        self.assertEqual(row.doc_invoice, "missing")
        self.assertFalse(row.docs_all_clear)
        self._row("SCALE", tx)
        self._row("INV", tx)
        self._row("CO", tx)
        self.assertTrue(self._dashboard(tx).docs_all_clear)

    def test_operation_row_never_clears_a_legacy_item(self):
        tx, loads = self._trade()
        self._row("BOL", loads, scope="BKG-1/r1")
        self._row("BOL", tx, scope="BKG-1/r1")
        row = self._dashboard(tx)
        self.assertEqual(row.doc_bol, "missing")

    def test_expired_or_superseded_legacy_row_is_not_ok(self):
        tx, loads = self._trade()
        bol = self._row("BOL", loads)
        self.assertEqual(self._dashboard(tx).doc_bol, "ok")
        later = fields.Date.today() + timedelta(days=30)
        bol.write({"expiry_date": fields.Date.today() + timedelta(days=1)})
        with patch.object(type(self.env["plasticos.document"]), "_evidence_today", return_value=later):
            self.assertEqual(self._dashboard(tx).doc_bol, "pending")
        replacement = self._row("BOL", tx, verify=False)
        bol.with_user(self.verifier).action_supersede(replacement.id)
        self.assertEqual(self._dashboard(tx).doc_bol, "pending")

    def test_native_branch_reads_the_native_projection_only_without_business_rows(self):
        tx, _loads = self._trade()
        folder = self.env.ref("plasticos_documents_native.folder_plasticos_inbox")
        self._create_native_document(
            self.env,
            name="native-bol.pdf",
            folder=folder,
            datas=base64.b64encode(b"%PDF-1.4 native checklist"),
            doc_type="bol",
            transaction=tx,
        )
        dashboard = type(self.env["plasticos.sales.dashboard"])
        self.assertEqual(self._dashboard(tx).doc_bol, "missing")
        with patch.object(dashboard, "_doc_checklist_source", lambda model: self._native_model_name()):
            self.assertEqual(self._dashboard(tx).doc_bol, "pending")
        with patch.object(dashboard, "_doc_checklist_source", lambda model: False):
            self.assertEqual(self._dashboard(tx).doc_bol, "missing")
