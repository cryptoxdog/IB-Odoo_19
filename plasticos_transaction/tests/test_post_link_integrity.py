"""Posting gate and transaction link integrity on account.move.action_post.

C1 (F-03): a vendor bill that resolves to a transaction passes the document check.
C2 (F-08): order lookups are company-scoped and never last-wins.
C3 (F-04): every refusal is raised before the native post; link bookkeeping
never rolls a posted move back and never replaces a customer invoice.
C5: an ambiguous origin is refused; an origin that names nothing posts unlinked.
C7: purchase order confirmation uses the same company-scoped lookup.
C8: the link write is system bookkeeping; the gates run as the posting user.
C9: a transaction number or delivery order number resolves; carrier bills are freight.
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
        credit = self._move("in_refund", "NO-SUCH-ORDER-C1")
        with self._hook_must_not_run():
            (no_match | no_transaction | no_origin | credit).action_post()
        for bill in no_match | no_transaction | no_origin | credit:
            self.assertEqual(bill.state, "posted")
            self.assertFalse(self.env["account.move"]._find_linked_transactions(bill.id))
        self.assertFalse(tx.vendor_bill_ids)

    # ── C2 / C5: company scope; an ambiguous origin is refused ───────

    def test_duplicate_sale_name_is_refused_and_never_last_wins(self):
        first, second = self._tx(), self._tx()
        sale = self._sale(first)
        self._sale(second, name=sale.name)
        invoice = self._move("out_invoice", sale.name)
        bill = self._move("in_invoice", sale.name)
        credit = self._move("in_refund", sale.name)
        for move in (invoice, bill, credit):
            with self._hook_must_not_run(), self.assertRaisesRegex(UserError, "more than one sale order is named"):
                move.action_post()
            self.assertEqual(move.state, "draft")
        self.assertFalse(first.customer_invoice_id | second.customer_invoice_id)
        self.assertFalse(first.vendor_bill_ids | second.vendor_bill_ids)

    def test_duplicate_purchase_name_is_refused(self):
        first, second = self._tx(), self._tx()
        purchase = self._purchase(first)
        self._purchase(second, name=purchase.name)
        bill = self._move("in_invoice", purchase.name)
        with self._hook_must_not_run(), self.assertRaisesRegex(UserError, "more than one purchase order is named"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")
        self.assertFalse(first.vendor_bill_ids | second.vendor_bill_ids)

    def test_purchase_held_by_two_transactions_is_refused(self):
        first, second = self._tx(), self._tx()
        purchase = self._purchase(first)
        second.purchase_order_ids = [(4, purchase.id)]
        bill = self._move("in_invoice", purchase.name)
        with self._hook_must_not_run(), self.assertRaisesRegex(UserError, "belongs to more than one transaction"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")
        self.assertFalse(first.vendor_bill_ids | second.vendor_bill_ids)

    def test_one_ambiguous_move_refuses_the_whole_batch_before_posting(self):
        first, second = self._tx(), self._tx()
        sale = self._sale(first)
        self._sale(second, name=sale.name)
        clean = self._move("in_invoice")
        ambiguous = self._move("in_invoice", sale.name)
        with self._documents(False), self.assertRaisesRegex(UserError, "is ambiguous"):
            (clean | ambiguous).action_post()
        self.assertEqual((clean | ambiguous).mapped("state"), ["draft", "draft"])

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

    # ── C8: the link is system bookkeeping; gates run as the user ────

    def _accountant(self):
        return self.env["res.users"].create(
            {
                "name": "Post Link Accountant",
                "login": "post_link_accountant",
                "group_ids": [
                    (6, 0, [self.env.ref("base.group_user").id, self.env.ref("account.group_account_invoice").id])
                ],
            }
        )

    def test_accountant_without_manager_group_posts_and_the_link_is_written(self):
        accountant = self._accountant()
        self.assertFalse(accountant.has_group("plasticos_transaction.group_plasticos_manager"))
        tx = self._tx()
        self.assertFalse(tx.with_user(accountant).has_access("write"))
        sale = self._sale(tx)
        invoice = self._move("out_invoice", sale.name)
        bill = self._move("in_invoice", sale.name)
        with self._documents(False):
            (invoice | bill).with_user(accountant).action_post()
        self.assertEqual((invoice | bill).mapped("state"), ["posted", "posted"])
        self.assertEqual(tx.customer_invoice_id, invoice)
        self.assertIn(bill, tx.vendor_bill_ids)

    def test_gates_still_apply_to_the_accountant(self):
        accountant = self._accountant()
        tx = self._tx()
        sale = self._sale(tx)
        bill = self._move("in_invoice", sale.name)
        with self._documents(True), self.assertRaisesRegex(UserError, "Missing required documents for vendor bill"):
            bill.with_user(accountant).action_post()
        self.assertEqual(bill.state, "draft")
        self.assertFalse(tx.vendor_bill_ids)
        tx._apply_close(tx)
        with self._documents(False), self.assertRaisesRegex(UserError, "cannot be attached to a closed trade"):
            bill.with_user(accountant).action_post()
        self.assertEqual(bill.state, "draft")
        self.assertFalse(tx.vendor_bill_ids)

    # ── C9: transaction number, delivery order number, carrier role ──

    def _carrier(self):
        return self.env["res.partner"].create({"name": "Post Link Carrier", "is_company": True, "supplier_rank": 1})

    def test_transaction_number_origin_resolves_invoice_and_bill(self):
        tx = self._tx()
        invoice = self._move("out_invoice", tx.name)
        bill = self._move("in_invoice", tx.name)
        with self._documents(True), self.assertRaisesRegex(UserError, "Missing required documents for vendor bill"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")
        with self._documents(False):
            (invoice | bill).action_post()
        self.assertEqual(tx.customer_invoice_id, invoice)
        self.assertIn(bill, tx.vendor_bill_ids)
        self.assertFalse(tx.freight_bill_ids)

    def test_carrier_bill_is_linked_as_freight_and_supplier_bill_as_vendor(self):
        carrier = self._carrier()
        tx = self._tx()
        tx.carrier_id = carrier
        freight = self._move("in_invoice", tx.name)
        freight.partner_id = carrier
        supplier_bill = self._move("in_invoice", tx.name)
        with self._documents(False):
            (freight | supplier_bill).action_post()
        self.assertEqual(tx.freight_bill_ids, freight)
        self.assertEqual(tx.vendor_bill_ids, supplier_bill)

    def test_carrier_that_is_also_the_supplier_stays_a_vendor_bill(self):
        tx = self._tx()
        tx.carrier_id = self.partner
        bill = self._move("in_invoice", tx.name)
        with self._documents(False):
            bill.action_post()
        self.assertEqual(tx.vendor_bill_ids, bill)
        self.assertFalse(tx.freight_bill_ids)

    def _delivery_order(self):
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        return self.env["stock.picking"].create(
            {"picking_type_id": warehouse.out_type_id.id, "partner_id": self.partner.id}
        )

    def test_delivery_order_number_resolves_a_carrier_bill(self):
        carrier = self._carrier()
        tx = self._tx()
        picking = self._delivery_order()
        tx.write({"carrier_id": carrier.id, "delivery_order_id": picking.id})
        self.assertEqual(tx.do_number, picking.name)
        bill = self._move("in_invoice", picking.name)
        bill.partner_id = carrier
        with self._documents(False):
            bill.action_post()
        self.assertEqual(tx.freight_bill_ids, bill)
        # A customer invoice is never resolved by a delivery order number.
        invoice = self._move("out_invoice", picking.name)
        with self._hook_must_not_run():
            invoice.action_post()
        self.assertFalse(tx.customer_invoice_id)

    def test_delivery_order_shared_by_two_transactions_is_refused(self):
        first, second = self._tx(), self._tx()
        picking = self._delivery_order()
        (first | second).write({"delivery_order_id": picking.id})
        bill = self._move("in_invoice", picking.name)
        with self._hook_must_not_run(), self.assertRaisesRegex(UserError, "leads to more than one transaction"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")

    def test_references_to_different_transactions_are_refused(self):
        by_sale, by_number = self._tx(), self._tx()
        self._sale(by_sale, name=by_number.name)
        bill = self._move("in_invoice", by_number.name)
        with self._hook_must_not_run(), self.assertRaisesRegex(UserError, "leads to more than one transaction"):
            bill.action_post()
        self.assertEqual(bill.state, "draft")

    def test_vendor_credit_resolves_gates_and_links(self):
        tx = self._tx()
        credit = self._move("in_refund", self._sale(tx).name)
        with self._documents(True), self.assertRaisesRegex(UserError, "Missing required documents for vendor bill"):
            credit.action_post()
        self.assertEqual(credit.state, "draft")
        with self._documents(False):
            credit.action_post()
        self.assertEqual(credit.state, "posted")
        self.assertIn(credit, tx.vendor_bill_ids)

    # ── C7: purchase order confirmation ──────────────────────────────

    def test_purchase_confirm_links_the_one_sale_order_transaction(self):
        tx = self._tx()
        sale = self._sale(tx)
        purchase = self._purchase(origin=sale.name)
        purchase.button_confirm()
        self.assertIn(purchase, tx.purchase_order_ids)

    def test_purchase_confirm_refuses_a_duplicate_sale_name(self):
        first, second = self._tx(), self._tx()
        sale = self._sale(first)
        self._sale(second, name=sale.name)
        purchase = self._purchase(origin=sale.name)
        with self.assertRaisesRegex(UserError, "more than one sale order is named"):
            purchase.button_confirm()
        self.assertEqual(purchase.state, "draft")
        self.assertNotIn(purchase, first.purchase_order_ids | second.purchase_order_ids)

    def test_purchase_confirm_ignores_a_sale_order_of_another_company(self):
        other_company = self.env["res.company"].create({"name": "Post Link Purchase Company"})
        self.env.user.company_ids = [(4, other_company.id)]
        foreign_tx = self._tx()
        foreign_sale = self._sale(foreign_tx, company_id=other_company.id)
        purchase = self._purchase(origin=foreign_sale.name)
        purchase.button_confirm()
        self.assertNotIn(purchase, foreign_tx.purchase_order_ids)
