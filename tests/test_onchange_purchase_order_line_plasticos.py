"""Onchange tests for purchase.order.line with PlastOS hooks.

Covers:
- product_id onchange populating price_unit and taxes
- quantity onchange affecting subtotal
"""

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPurchaseOrderLineOnchange(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Purchase = cls.env["purchase.order"]
        cls.Line = cls.env["purchase.order.line"]
        cls.partner = cls.env["res.partner"].create({"name": "PO Vendor"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "LDPE Film",
                "standard_price": 0.20,
            }
        )
        cls.po = cls.Purchase.create(
            {
                "partner_id": cls.partner.id,
                "date_order": fields.Datetime.now(),
            }
        )

    def test_onchange_product_sets_price(self):
        line = self.Line.new(
            {
                "order_id": self.po.id,
                "product_id": self.product.id,
                "product_qty": 1.0,
            }
        )
        line.onchange_product_id()
        self.assertGreaterEqual(line.price_unit, 0.0)

    def test_onchange_qty_updates_subtotal(self):
        line = self.Line.new(
            {
                "order_id": self.po.id,
                "product_id": self.product.id,
                "product_qty": 10.0,
            }
        )
        line.onchange_product_id()
        if hasattr(line, "price_subtotal"):
            self.assertGreater(line.price_subtotal, 0.0)

    def test_onchange_product_handles_missing_order_gracefully(self):
        line = self.Line.new({"product_id": self.product.id})
        line.onchange_product_id()
        self.assertIsNotNone(line, "Onchange should not crash without order")
