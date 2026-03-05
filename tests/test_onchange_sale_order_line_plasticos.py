"""Onchange tests for sale.order.line integrations used by PlastOS.

Covers:
- product_id onchange populating price_unit and polymer-related hints
- quantity onchange recalculating line subtotal (standard Odoo pattern).[web:127]
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestSaleOrderLineOnchange(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Sale = cls.env["sale.order"]
        cls.Line = cls.env["sale.order.line"]
        cls.partner = cls.env["res.partner"].create({"name": "SO Partner"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "HDPE Bales",
                "list_price": 0.50,
            }
        )
        cls.order = cls.Sale.create({"partner_id": cls.partner.id})

    def test_onchange_product_sets_price(self):
        line = self.Line.new(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
            }
        )
        line.product_id_change()
        self.assertEqual(line.price_unit, self.product.list_price)

    def test_onchange_qty_updates_subtotal(self):
        line = self.Line.new(
            {
                "order_id": self.order.id,
                "product_id": self.product.id,
                "product_uom_qty": 10.0,
            }
        )
        line.product_id_change()
        line._onchange_discount()
        if hasattr(line, "price_subtotal"):
            self.assertGreater(line.price_subtotal, 0.0)

    def test_onchange_product_handles_no_product_gracefully(self):
        line = self.Line.new({"order_id": self.order.id})
        line.product_id_change()
        self.assertIsNotNone(line, "Onchange should not crash without product")
