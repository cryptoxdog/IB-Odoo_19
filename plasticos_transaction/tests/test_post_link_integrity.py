"""Posting gate and transaction link integrity on account.move.action_post.

C1 (F-03): a vendor bill that resolves to a transaction passes the document check.
C2 (F-08): order lookups are company-scoped; an ambiguous name creates no link.
C3 (F-04): every refusal is raised before the native post; link bookkeeping
never rolls a posted move back and never replaces a customer invoice.
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import tagged


def _plasticos_test_case():
    from odoo.addons.plasticos_base.test_common import PlasticosTestCase

    return PlasticosTestCase


@tagged("post_install", "-at_install", "accounting")
class TestPostLinkIntegrity(_plasticos_test_case()):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Post Link Partner", "is_company": True, "customer_rank": 1, "supplier_rank": 1}
        )

    # ── fixtures ─────────────────────────────────────────────────────

    def _tx(self):
        return self.env["plasticos.transaction"].create(
            {"supplier_id": self.partner.id, "buyer_id": self.partner.id, "quantity": 1}
        )

    def _sale(self, tx=None, **vals):
        values = {"partner_id": self.partner.id, **vals}
        if tx:
            values["transaction_id"] = tx.id
        return self.env["sale.order"].create(values)

    def _purchase(self, tx=None, **vals):
        order = self.env["purchase.order"].create({"partner_id": self.partner.id, **vals})
        if tx:
            tx.purchase_order_ids = [(4, order.id)]
        return order

    def _move(self, move_type, origin=None):
        vals = {
            "move_type": move_type,
            "partner_id": self.partner.id,
            "invoice_date": "2026-11-12",
            "invoice_line_ids": [(0, 0, {"name": "Line", "quantity": 1, "price_unit": 50.0})],
        }
        if origin:
            vals["invoice_origin"] = origin
        return self.env["account.move"].create(vals)

    def _documents(self, missing):
        """Pin the documents hook: the gate under test is the caller, not the rule engine."""
        return patch.object(type(self.env["account.move"]), "_missing_invoice_documents", return_value=missing)

    def _hook_must_not_run(self):
        return patch.object(
            type(self.env["account.move"]),
            "_missing_invoice_documents",
            side_effect=AssertionError("document hook ran for an unresolved move"),
        )

    def _notes(self, move):
        return " ".join(move.message_ids.mapped("body"))

    # ── C1: vendor bills pass the document gate ──────────────────────

    def test_vendor_bill_by_sale_origin_is_blocked_when_documents_missing(self):
        tx = self._tx()
        bill = self._move("in_invoice", self._sale(tx).name)
        with self._documents(True), self.assertRaisesRegex(UserError, "Missing required documents for vendor bill"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")
        self.assertNotIn(bill, tx.vendor_bill_ids)

    def test_vendor_bill_by_purchase_origin_is_blocked_when_documents_missing(self):
        tx = self._tx()
        bill = self._move("in_invoice", self._purchase(tx).name)
        with self._documents(True), self.assertRaisesRegex(UserError, "Missing required documents for vendor bill"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")
        self.assertNotIn(bill, tx.vendor_bill_ids)

    def test_compliant_vendor_bill_posts_and_links(self):
        tx = self._tx()
        by_sale = self._move("in_invoice", self._sale(tx).name)
        other = self._tx()
        by_purchase = self._move("in_invoice", self._purchase(other).name)
        with self._documents(False):
            (by_sale | by_purchase).action_post()
        self.assertEqual(by_sale.state, "posted")
        self.assertEqual(by_purchase.state, "posted")
        self.assertIn(by_sale, tx.vendor_bill_ids)
        self.assertIn(by_purchase, other.vendor_bill_ids)

    def test_unresolved_origin_posts_natively_without_link_or_gate(self):
        tx = self._tx()
        unlinked_purchase = self._purchase()
        no_match = self._move("in_invoice", "NO-SUCH-ORDER-C1")
        no_transaction = self._move("in_invoice", unlinked_purchase.name)
        no_origin = self._move("in_invoice")
        with self._hook_must_not_run():
            (no_match | no_transaction | no_origin).action_post()
        for bill in no_match | no_transaction | no_origin:
            self.assertEqual(bill.state, "posted")
            self.assertFalse(self.env["account.move"]._find_linked_transactions(bill.id))
        self.assertFalse(tx.vendor_bill_ids)

    # ── C2: company scope and ambiguity ──────────────────────────────

    def test_duplicate_sale_name_is_ambiguous_and_never_last_wins(self):
        first, second = self._tx(), self._tx()
        sale = self._sale(first)
        self._sale(second, name=sale.name)
        invoice = self._move("out_invoice", sale.name)
        bill = self._move("in_invoice", sale.name)
        with self._hook_must_not_run():
            (invoice | bill).action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(bill.state, "posted")
        self.assertFalse(first.customer_invoice_id | second.customer_invoice_id)
        self.assertFalse(first.vendor_bill_ids | second.vendor_bill_ids)
        self.assertIn("more than one sale order is named", self._notes(invoice))
        self.assertIn("more than one sale order is named", self._notes(bill))

    def test_duplicate_purchase_name_is_ambiguous(self):
        first, second = self._tx(), self._tx()
        purchase = self._purchase(first)
        self._purchase(second, name=purchase.name)
        bill = self._move("in_invoice", purchase.name)
        with self._hook_must_not_run():
            bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(first.vendor_bill_ids | second.vendor_bill_ids)
        self.assertIn("more than one purchase order is named", self._notes(bill))

    def test_purchase_held_by_two_transactions_is_ambiguous(self):
        first, second = self._tx(), self._tx()
        purchase = self._purchase(first)
        second.purchase_order_ids = [(4, purchase.id)]
        bill = self._move("in_invoice", purchase.name)
        with self._hook_must_not_run():
            bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(first.vendor_bill_ids | second.vendor_bill_ids)
        self.assertIn("belongs to more than one transaction", self._notes(bill))

    def test_order_of_another_company_is_not_resolved(self):
        other_company = self.env["res.company"].create({"name": "Post Link Other Company"})
        self.env.user.company_ids = [(4, other_company.id)]
        foreign_tx = self._tx()
        foreign_sale = self._sale(foreign_tx, company_id=other_company.id)
        invoice = self._move("out_invoice", foreign_sale.name)
        self.assertNotEqual(invoice.company_id, other_company)
        with self._hook_must_not_run():
            invoice.action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertFalse(foreign_tx.customer_invoice_id)

        # Same name in the move's own company resolves to that order only.
        local_tx = self._tx()
        self._sale(local_tx, name=foreign_sale.name)
        local_invoice = self._move("out_invoice", foreign_sale.name)
        with self._documents(False):
            local_invoice.action_post()
        self.assertEqual(local_tx.customer_invoice_id, local_invoice)
        self.assertFalse(foreign_tx.customer_invoice_id)

    # ── C3: refusals precede the post; links never roll it back ──────

    def test_second_customer_invoice_posts_and_keeps_the_first_pointer(self):
        tx = self._tx()
        sale = self._sale(tx)
        first = self._move("out_invoice", sale.name)
        second = self._move("out_invoice", sale.name)
        with self._documents(False):
            first.action_post()
            self.assertEqual(tx.customer_invoice_id, first)
            second.action_post()
        self.assertEqual(second.state, "posted")
        self.assertEqual(tx.customer_invoice_id, first)
        self.assertIn("already has customer invoice", self._notes(second))
        self.assertNotIn("Posted without a transaction link", self._notes(first))

    def test_two_customer_invoices_in_one_batch_link_only_the_first(self):
        tx = self._tx()
        sale = self._sale(tx)
        first = self._move("out_invoice", sale.name)
        second = self._move("out_invoice", sale.name)
        with self._documents(False):
            (first | second).action_post()
        self.assertEqual((first | second).mapped("state"), ["posted", "posted"])
        self.assertEqual(tx.customer_invoice_id, first)
        self.assertIn("already has customer invoice", self._notes(second))

    def test_second_customer_invoice_still_passes_the_document_gate(self):
        tx = self._tx()
        sale = self._sale(tx)
        first = self._move("out_invoice", sale.name)
        with self._documents(False):
            first.action_post()
        second = self._move("out_invoice", sale.name)
        with self._documents(True), self.assertRaisesRegex(UserError, "Missing required documents for invoice"):
            second.action_post()
        self.assertEqual(second.state, "draft")

    def test_vendor_bill_for_closed_transaction_is_refused_before_posting(self):
        tx = self._tx()
        sale = self._sale(tx)
        tx._apply_close(tx)
        self.assertEqual(tx.state, "closed")
        bill = self._move("in_invoice", sale.name)
        with self._documents(False), self.assertRaisesRegex(UserError, "cannot be attached to a closed trade"):
            bill.action_post()
        # No savepoint wraps the call: a draft state proves the native post never ran.
        self.assertEqual(bill.state, "draft")
        self.assertFalse(tx.vendor_bill_ids)

    def test_bill_held_by_another_transaction_posts_without_moving(self):
        owner, resolved = self._tx(), self._tx()
        bill = self._move("in_invoice", self._sale(resolved).name)
        owner.vendor_bill_ids = [(4, bill.id)]
        with self._documents(False):
            bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertIn(bill, owner.vendor_bill_ids)
        self.assertNotIn(bill, resolved.vendor_bill_ids)
        self.assertIn("already linked to another transaction", self._notes(bill))

    def test_freight_bill_of_the_same_transaction_is_not_also_a_vendor_bill(self):
        tx = self._tx()
        bill = self._move("in_invoice", self._sale(tx).name)
        tx.freight_bill_ids = [(4, bill.id)]
        with self._documents(False):
            bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertIn(bill, tx.freight_bill_ids)
        self.assertNotIn(bill, tx.vendor_bill_ids)
