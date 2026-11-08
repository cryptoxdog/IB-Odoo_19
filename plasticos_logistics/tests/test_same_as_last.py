"""Same As Last copies the last completed deal and changes only the dates."""

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

    def _completed_deal(self):
        sale = self.env["sale.order"].create(
            {
                "partner_id": self.buyer.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 10.0, "price_unit": 0.25})],
            }
        )
        purchase = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier.id,
                "order_line": [(0, 0, {"product_id": self.product.id, "product_qty": 10.0, "price_unit": 0.12})],
            }
        )
        transaction = self.env["plasticos.transaction"].create(
            {
                "name": "TX-SAL-SOURCE",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": sale.id,
                "purchase_order_ids": [(6, 0, [purchase.id])],
                "delivery_term": "appointment",
                "state": "delivered",
            }
        )
        load = self.env["plasticos.load"].create(
            {
                "sale_order_id": sale.id,
                "carrier_id": self.carrier.id,
                "rate_amount": 1800.0,
                "rate_currency_id": self.env.company.currency_id.id,
                "freight_context_fingerprint": False,
            }
        )
        self.assertFalse(load.freight_context_fingerprint)
        self.assertEqual(load.transaction_id, transaction)
        return transaction

    def test_a_deal_without_a_booking_fingerprint_copies_as_drafts_dated_today(self):
        source = self._completed_deal()
        action = source.action_same_as_last()
        new_sale = self.env["sale.order"].browse(action["res_id"])
        self.assertEqual(new_sale.state, "draft")
        self.assertNotEqual(new_sale, source.sale_order_id)
        self.assertEqual(new_sale.partner_id, self.buyer)
        self.assertEqual(new_sale.order_line.product_id, self.product)
        self.assertEqual(new_sale.order_line.product_uom_qty, 10.0)
        self.assertAlmostEqual(new_sale.order_line.price_unit, 0.25)
        self.assertEqual(new_sale.date_order.date(), fields.Datetime.now().date())
        new_purchase = self.env["purchase.order"].search([("origin", "=", f"SAL:{source.sale_order_id.id}")])
        self.assertEqual(len(new_purchase), 1)
        self.assertEqual(new_purchase.state, "draft")
        self.assertEqual(new_purchase.partner_id, self.supplier)
        self.assertEqual(new_purchase.order_line.product_id, self.product)
        self.assertAlmostEqual(new_purchase.order_line.price_unit, 0.12)
        self.assertEqual(new_purchase.date_order.date(), fields.Datetime.now().date())
        new_load = self.env["plasticos.load"].search([("sale_order_id", "=", new_sale.id)])
        self.assertEqual(len(new_load), 1)
        self.assertEqual(new_load.state, "draft")
        self.assertEqual(new_load.carrier_id, self.carrier)
        self.assertAlmostEqual(new_load.rate_amount, 1800.0)
        self.assertFalse(new_load.freight_context_fingerprint)
        with self.assertRaises(UserError):
            source.action_same_as_last()

    def test_a_completed_deal_without_a_purchase_order_is_refused(self):
        source = self._completed_deal()
        sale = self.env["sale.order"].create({"partner_id": self.buyer.id})
        newer = self.env["plasticos.transaction"].create(
            {
                "name": "TX-SAL-NO-PO",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": sale.id,
                "delivery_term": "appointment",
                "state": "closed",
            }
        )
        self.assertGreater(newer.id, source.id)
        with self.assertRaises(UserError):
            source.action_same_as_last()
        self.assertFalse(self.env["sale.order"].search([("origin", "=", f"SAL:{sale.id}")]))
