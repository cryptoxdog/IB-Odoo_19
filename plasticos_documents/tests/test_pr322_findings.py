"""PR #322 re-audit: eligibility, company, expiry, and partial Receiving."""

import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_documents_native.tests.test_native_search_parity import (
    TestNativeSearchParity,
)
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "documents", "pr322")
class TestPr322Findings(PlasticosTestCase):
    """Discriminating cases for the five Documents findings. No invented allocation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Finding Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )
        cls.company_b = cls.env["res.company"].create({"name": "Finding Company B"})
        internal = cls.env.ref("base.group_user")
        verifier = cls.env.ref("plasticos_documents.group_documents_user")
        purchase = cls.env.ref("purchase.group_purchase_user")
        cls.verifier = cls.env["res.users"].create(
            {
                "name": "Finding Verifier",
                "login": "pr322_finding_verifier",
                "group_ids": [(6, 0, [internal.id, verifier.id, purchase.id])],
            }
        )
        cls.internal = cls.env["res.users"].create(
            {
                "name": "Finding Internal",
                "login": "pr322_finding_internal",
                "group_ids": [(6, 0, [internal.id])],
            }
        )
        cls.bol = cls.env["plasticos.document.tag"].search([("code", "=", "BOL")], limit=1)
        cls.receiving = cls.env["plasticos.document.tag"].search([("code", "=", "RECEIVING")], limit=1)
        cls.cst = cls.env["plasticos.document.tag"].search([("code", "=", "CST")], limit=1)
        if not cls.bol or not cls.receiving or not cls.cst:
            raise AssertionError("BLOCKED: BOL, RECEIVING, or CST tag is not installed")

    def _attachment(self):
        return self.env["ir.attachment"].create(
            {
                "name": "finding.txt",
                "datas": base64.b64encode(b"finding-bytes"),
                "res_model": "plasticos.document",
                "res_id": 0,
            }
        )

    def _shell(self, tag):
        return self.env["plasticos.document"].create(
            {
                "name": tag.code,
                "tag_id": tag.id,
                "res_model": "documents.document",
                "res_id": 0,
                "attachment_id": self._attachment().id,
            }
        )

    def _accept(self, tag, transaction, quantity):
        shell = self._shell(tag)
        return shell.with_user(self.verifier).action_associate(
            "plasticos.transaction",
            transaction.id,
            source_reference=f"finding-{tag.code}",
            covered_quantity=quantity,
        )

    def _only_rule(self, tag):
        self.env["plasticos.document.rule"].search([("res_model", "=", "plasticos.transaction")]).write(
            {"active": False}
        )
        return self.env["plasticos.document.rule"].create(
            {
                "name": f"finding {tag.code}",
                "tag_id": tag.id,
                "res_model": "plasticos.transaction",
                "required_for_invoice": True,
                "required_for_close": False,
            }
        )

    def _transaction(self, quantity=44000, **extra):
        vals = {"supplier_id": self.partner.id, "buyer_id": self.partner.id, "quantity": quantity}
        vals.update(extra)
        return self.env["plasticos.transaction"].create(vals)

    def test_forged_receiving_tag_cannot_reuse_bol_approval(self):
        tx = self._transaction()
        self._only_rule(self.receiving)
        row = self._accept(self.bol, tx, quantity=44000)
        row.with_user(self.verifier).action_verify()
        actor = row.verified_by
        stamp = row.verified_at
        service = self.env["plasticos.compliance.service"]
        self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        with self.assertRaises(AccessError):
            row.with_user(self.internal).write({"tag_id": self.receiving.id})
        with self.assertRaises(AccessError):
            row.with_user(self.verifier).write({"tag_id": self.receiving.id, "doc_category": "buyer"})
        self.assertEqual(row.tag_id, self.bol)
        self.assertEqual(row.verified_by, actor)
        self.assertEqual(row.verified_at, stamp)
        self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))

    def test_unprivileged_write_cannot_revive_superseded_evidence(self):
        tx = self._transaction(quantity=10)
        self._only_rule(self.bol)
        row = self._accept(self.bol, tx, quantity=0)
        row.with_user(self.verifier).action_verify()
        actor = row.verified_by
        stamp = row.verified_at
        replacement = self._shell(self.bol)
        row.with_user(self.verifier).action_supersede(replacement.id)
        self.assertFalse(row._currently_eligible())
        self.assertEqual(row.verified_by, actor)
        self.assertEqual(row.verified_at, stamp)
        with self.assertRaises(AccessError):
            row.with_user(self.internal).write({"is_current": True, "superseded_by": False})
        with self.assertRaises(AccessError):
            row.with_user(self.verifier).write({"is_current": True})
        self.assertFalse(row.is_current)
        self.assertEqual(row.superseded_by, replacement)
        self.assertEqual(row.verified_by, actor)

    def test_authorized_supersede_preserves_history_and_new_decision_restores(self):
        tx = self._transaction(quantity=10)
        self._only_rule(self.bol)
        row = self._accept(self.bol, tx, quantity=0)
        row.with_user(self.verifier).action_verify()
        actor = row.verified_by
        stamp = row.verified_at
        replacement = self._accept(self.bol, tx, quantity=0)
        row.with_user(self.verifier).action_supersede(replacement.id)
        self.assertEqual(row.verified_by, actor)
        self.assertEqual(row.verified_at, stamp)
        self.assertFalse(row._currently_eligible())
        replacement.with_user(self.verifier).action_verify()
        self.assertTrue(replacement._currently_eligible())
        self.assertEqual(row.verified_by, actor)
        self.assertTrue(
            self.env["plasticos.compliance.service"].is_compliant("plasticos.transaction", tx.id, purpose="invoice")
        )

    def test_company_a_clerk_cannot_accept_company_b_sale_or_a_conflict(self):
        sale_b = (
            self.env["sale.order"]
            .with_company(self.company_b)
            .create({"partner_id": self.partner.id, "company_id": self.company_b.id})
        )
        foreign = self._transaction(sale_order_id=sale_b.id)
        shell = self._shell(self.bol)
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            shell.with_user(self.verifier).action_associate(
                "plasticos.transaction", foreign.id, source_reference="company-b"
            )
        self.assertFalse(shell.verified)
        sale_a = self.env["sale.order"].create({"partner_id": self.partner.id})
        purchase_b = (
            self.env["purchase.order"]
            .with_company(self.company_b)
            .create({"partner_id": self.partner.id, "company_id": self.company_b.id})
        )
        conflict = self._transaction(
            sale_order_id=sale_a.id,
            purchase_order_ids=[(6, 0, [purchase_b.id])],
        )
        with self.assertRaisesRegex(UserError, "companies conflict"):
            self._shell(self.bol).with_user(self.verifier).action_associate(
                "plasticos.transaction", conflict.id, source_reference="conflict"
            )
        matched = self._transaction(sale_order_id=sale_a.id)
        accepted = (
            self._shell(self.bol)
            .with_user(self.verifier)
            .action_associate("plasticos.transaction", matched.id, source_reference="company-a")
        )
        self.assertEqual(accepted.subject_company_id, sale_a.company_id)
        self.assertNotEqual(accepted.subject_company_id, self.company_b)
        with self.assertRaisesRegex(UserError, "sudo"):
            self._shell(self.bol).with_user(self.verifier).sudo().action_associate(
                "plasticos.transaction", matched.id, source_reference="sudo"
            )
        refused = False
        try:
            self._shell(self.bol).with_user(self.verifier).with_company(self.company_b).action_associate(
                "plasticos.transaction", foreign.id, source_reference="with-company"
            )
        except (AccessError, UserError):
            refused = True
        self.assertTrue(refused)

    def test_same_partner_name_and_native_navigation_do_not_cross_companies(self):
        name = "Shared Finding Vendor"
        partner_a = self.env["res.partner"].create({"name": name, "is_company": True, "supplier_rank": 1})
        partner_b = self.env["res.partner"].create(
            {"name": name, "is_company": True, "supplier_rank": 1, "company_id": self.company_b.id}
        )
        self.assertEqual(partner_a.name, partner_b.name)
        self.assertNotEqual(partner_a, partner_b)
        purchase_b = (
            self.env["purchase.order"]
            .with_company(self.company_b)
            .create({"partner_id": partner_b.id, "company_id": self.company_b.id})
        )
        shell = self._shell(self.bol)
        shell.candidate_partner_id = partner_a
        with self.assertRaisesRegex(UserError, "UNRESOLVED"):
            shell.with_user(self.verifier).action_associate(
                "purchase.order", purchase_b.id, source_reference="same-name"
            )
        self.assertFalse(
            self.env["plasticos.document"].search(
                [
                    ("res_model", "=", "purchase.order"),
                    ("res_id", "=", purchase_b.id),
                    ("association_state", "=", "accepted"),
                ]
            )
        )

    def test_partial_receiving_does_not_authorize_the_full_invoice(self):
        tx = self._transaction(quantity=44000)
        self._only_rule(self.receiving)
        sale = self.env["sale.order"].create({"partner_id": self.partner.id, "transaction_id": tx.id})
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_origin": sale.name,
                "invoice_date": "2026-10-28",
                "invoice_line_ids": [(0, 0, {"name": "Buyer", "quantity": 1, "price_unit": 10.0})],
            }
        )
        service = self.env["plasticos.compliance.service"]
        partial = self._accept(self.receiving, tx, quantity=20000)
        other = self._accept(self.receiving, tx, quantity=24000)
        partial.with_user(self.verifier).action_verify()
        other.with_user(self.verifier).action_verify()
        cst = self._accept(self.cst, tx, quantity=44000)
        cst.with_user(self.verifier).action_verify()
        posts = []
        with patch.object(type(invoice), "action_post", side_effect=lambda *args, **kwargs: posts.append(1)):
            self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        self.assertFalse(posts)
        with self.assertRaisesRegex(UserError, "Missing required documents"):
            invoice.action_post()
        self.assertEqual(invoice.state, "draft")
        zero = self._accept(self.receiving, tx, quantity=0)
        zero.with_user(self.verifier).action_verify()
        self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        full = self._accept(self.receiving, tx, quantity=44000)
        full.with_user(self.verifier).action_verify()
        self.assertTrue(full._currently_eligible())
        self.assertTrue(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))

    def test_calendar_expiry_updates_stored_compliance_without_a_document_write(self):
        tx = self._transaction(quantity=10)
        self._only_rule(self.bol)
        row = self._shell(self.bol)
        row.expiry_date = fields.Date.today() + timedelta(days=1)
        accepted = row.with_user(self.verifier).action_associate(
            "plasticos.transaction", tx.id, source_reference="expires-tomorrow", covered_quantity=0
        )
        accepted.with_user(self.verifier).action_verify()
        actor = accepted.verified_by
        stamp = accepted.verified_at
        service = self.env["plasticos.compliance.service"]
        self.assertTrue(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
        later = fields.Date.today() + timedelta(days=2)
        write_date = accepted.write_date
        with patch.object(type(accepted), "_evidence_today", return_value=later):
            self.assertFalse(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))
            self.assertEqual(accepted.write_date, write_date)
            self.assertEqual(accepted.verified_by, actor)
            self.assertEqual(accepted.verified_at, stamp)
            self.env.flush_all()
            self.env.cr.execute("SELECT compliance_status FROM plasticos_transaction WHERE id = %s", (tx.id,))
            self.assertEqual(self.env.cr.fetchone()[0], "compliant")
            found = (
                self.env["plasticos.transaction"]
                .with_context(plasticos_documents_today=later)
                .search([("id", "=", tx.id), ("compliance_status", "=", "compliant")])
            )
            self.assertEqual(found, tx)
            self.env["plasticos.midnight.recompute"]._recompute_document_expiry()
            self.env.flush_all()
            self.env.cr.execute("SELECT compliance_status FROM plasticos_transaction WHERE id = %s", (tx.id,))
            self.assertEqual(self.env.cr.fetchone()[0], "missing")
        self.assertEqual(accepted.verified_by, actor)
        self.assertEqual(accepted.verified_at, stamp)
        self.assertEqual(accepted.expiry_date, fields.Date.today() + timedelta(days=1))
        replacement = self._accept(self.bol, tx, quantity=0)
        replacement.with_user(self.verifier).action_verify()
        self.assertEqual(accepted.verified_by, actor)
        self.assertTrue(service.is_compliant("plasticos.transaction", tx.id, purpose="invoice"))

    def test_pending_tag_edit_stays_open_before_a_decision(self):
        tx = self._transaction(quantity=10)
        row = self._accept(self.bol, tx, quantity=0)
        row.with_user(self.verifier).write({"tag_id": self.receiving.id})
        self.assertEqual(row.tag_id, self.receiving)
        self.assertFalse(row.verified)


class TestPr322NativeSearch(TestNativeSearchParity):
    """Run the native search truth table inside the Documents suite."""

    allow_inherited_tests_method = True
