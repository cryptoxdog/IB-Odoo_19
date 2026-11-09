"""Same As Last copies the last completed deal as one complete draft deal; only the dates change."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSameAsLast(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.buyer = cls.env["res.partner"].create({"name": "SAL Buyer", "is_company": True, "customer_rank": 1})
        cls.supplier = cls.env["res.partner"].create({"name": "SAL Supplier", "is_company": True, "supplier_rank": 1})
        cls.carrier = cls.env["res.partner"].create({"name": "SAL Carrier", "is_company": True})
        cls.product = cls.env["product.product"].create(
            {"name": "SAL Regrind", "type": "consu", "sale_ok": True, "purchase_ok": True}
        )
        cls.currency = cls.env.company.currency_id

    def _purchase(self, price):
        return self.env["purchase.order"].create(
            {
                "partner_id": self.supplier.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 10.0, "price_unit": price})],
            }
        )

    def _completed_deal(self, purchase_prices=(0.12,), load_rates=(1800.0,)):
        sale = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 10.0, "price_unit": 0.25})],
            }
        )
        purchases = self.env["purchase.order"]
        for price in purchase_prices:
            purchases |= self._purchase(price)
        transaction = self.env["plasticos.transaction"].create(
            {
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "carrier_id": self.carrier.id,
                "sale_order_id": sale.id,
                "purchase_order_ids": [(6, 0, purchases.ids)],
                "product_id": self.product.id,
                "quantity": 10.0,
                "unit_price": 0.25,
                "freight_rate": 1800.0,
                "delivery_term": "appointment",
            }
        )
        sale.transaction_id = transaction.id
        for rate in load_rates:
            load = self.env["plasticos.load"].create(
                {
                    "sale_order_id": sale.id,
                    "carrier_id": self.carrier.id,
                    "rate_amount": rate,
                    "rate_currency_id": self.currency.id,
                }
            )
            self.assertFalse(load.freight_context_fingerprint)
            self.assertEqual(load.transaction_id, transaction)
        transaction.with_context(bypass_state_guard=True).write({"state": "delivered"})
        return transaction

    def _copy(self, source):
        action = source.action_same_as_last()
        self.assertEqual(action["res_model"], "plasticos.transaction")
        return self.env["plasticos.transaction"].browse(action["res_id"])

    def test_the_copy_is_one_complete_draft_deal_dated_today(self):
        source = self._completed_deal()
        has_approval = "approved" in source.sale_order_id._fields
        if has_approval:
            source.sale_order_id.approved = True
        deal = self._copy(source)
        today = fields.Datetime.now().date()

        self.assertNotEqual(deal, source)
        self.assertEqual(deal.state, "draft")
        self.assertEqual((deal.buyer_id, deal.supplier_id, deal.carrier_id), (self.buyer, self.supplier, self.carrier))
        self.assertEqual(deal.product_id, self.product)
        self.assertAlmostEqual(deal.unit_price, 0.25)
        self.assertAlmostEqual(deal.freight_rate, 1800.0)
        self.assertEqual(deal.delivery_term, "appointment")

        new_sale = deal.sale_order_id
        self.assertNotEqual(new_sale, source.sale_order_id)
        self.assertEqual(new_sale.state, "draft")
        self.assertEqual(new_sale.transaction_id, deal, "the copy must not point at the source transaction")
        self.assertEqual(new_sale.origin, f"SAL:{source.sale_order_id.id}")
        self.assertEqual(new_sale.partner_id, self.buyer)
        self.assertEqual(new_sale.order_line.product_id, self.product)
        self.assertEqual(new_sale.order_line.product_uom_qty, 10.0)
        self.assertAlmostEqual(new_sale.order_line.price_unit, 0.25)
        self.assertEqual(new_sale.date_order.date(), today)
        self.assertEqual(source.sale_order_id.transaction_id, source)
        if has_approval:
            self.assertFalse(new_sale.approved, "a copied sale order must earn its own approval")

        new_purchase = deal.purchase_order_ids
        self.assertEqual(len(new_purchase), 1)
        self.assertFalse(new_purchase & source.purchase_order_ids)
        self.assertEqual(new_purchase.state, "draft")
        self.assertEqual(new_purchase.origin, new_sale.name)
        self.assertEqual(new_purchase.partner_id, self.supplier)
        self.assertAlmostEqual(new_purchase.order_line.price_unit, 0.12)
        self.assertEqual(new_purchase.date_order.date(), today)

        self.assertEqual(len(deal.load_ids), 1)
        self.assertEqual(deal.load_ids.sale_order_id, new_sale)
        self.assertEqual(deal.load_ids.state, "draft")
        self.assertEqual(deal.load_ids.carrier_id, self.carrier)
        self.assertAlmostEqual(deal.load_ids.rate_amount, 1800.0)
        self.assertFalse(deal.load_ids.freight_context_fingerprint)
        self.assertEqual(len(source.load_ids), 1, "the source keeps its own load")

    def test_every_purchase_order_and_every_load_is_copied(self):
        source = self._completed_deal(purchase_prices=(0.12, 0.11), load_rates=(1800.0, 1950.0))
        deal = self._copy(source)
        self.assertEqual(len(deal.purchase_order_ids), 2)
        self.assertEqual(sorted(deal.purchase_order_ids.order_line.mapped("price_unit")), [0.11, 0.12])
        self.assertFalse(deal.purchase_order_ids & source.purchase_order_ids)
        self.assertEqual(sorted(deal.load_ids.mapped("rate_amount")), [1800.0, 1950.0])
        self.assertEqual(deal.load_ids.sale_order_id, deal.sale_order_id)

    def test_a_deal_without_loads_copies_without_loads(self):
        source = self._completed_deal(load_rates=())
        deal = self._copy(source)
        self.assertFalse(deal.load_ids)
        self.assertTrue(deal.sale_order_id and deal.purchase_order_ids)

    def test_an_open_copy_refuses_another_and_a_cancelled_copy_does_not(self):
        source = self._completed_deal()
        first = self._copy(source)
        with self.assertRaises(UserError):
            source.action_same_as_last()
        self.assertEqual(
            self.env["plasticos.transaction"].search_count([("sale_order_id.origin", "=", first.sale_order_id.origin)]),
            1,
        )
        first.sale_order_id.action_cancel()
        second = self._copy(source)
        self.assertNotEqual(second, first)

    def test_confirming_the_copied_sale_order_compiles_no_second_transaction(self):
        source = self._completed_deal()
        deal = self._copy(source)
        deal.sale_order_id.action_confirm()
        self.assertEqual(deal.sale_order_id.transaction_id, deal)
        self.assertEqual(
            self.env["plasticos.transaction"].search_count([("sale_order_id", "=", deal.sale_order_id.id)]), 1
        )

    def test_a_completed_deal_without_a_purchase_order_is_refused(self):
        source = self._completed_deal()
        sale = self.env["sale.order"].create({"partner_id": self.buyer.id})
        newer = self.env["plasticos.transaction"].create(
            {
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": sale.id,
                "delivery_term": "appointment",
            }
        )
        newer.with_context(bypass_state_guard=True).write({"state": "closed"})
        self.assertGreater(newer.id, source.id)
        before = self.env["plasticos.transaction"].search_count([])
        with self.assertRaises(UserError):
            source.action_same_as_last()
        self.assertFalse(self.env["sale.order"].search([("origin", "=", f"SAL:{sale.id}")]))
        self.assertEqual(self.env["plasticos.transaction"].search_count([]), before)
