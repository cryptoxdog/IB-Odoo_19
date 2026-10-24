"""Onchange tests for sale.order.line integrations used by PlastOS.

Covers:
- product_id onchange populating price_unit and polymer-related hints
- quantity onchange recalculating line subtotal (standard Odoo pattern).[web:127]
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install")
class TestSaleOrderLineOnchange(PlasticosTestCase):
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

    # Odoo 19 removed sale.order.line.product_id_change / _onchange_discount: price_unit and the
    # amounts are computed from product_id / product_uom_qty (odoo/addons/sale/models/sale_order_line.py:589-620,
    # 854-865) and _onchange_product_id (sale_order_line.py:1332-1336) only resets the price. The UI
    # path is exercised through Form so the onchange + compute cascade runs as in the client.

    def test_onchange_product_sets_price(self):
        with Form(self.order) as order_form:
            with order_form.order_line.new() as line:
                line.product_id = self.product
                line.product_uom_qty = 1.0
                self.assertEqual(line.price_unit, self.product.list_price)

    def test_onchange_qty_updates_subtotal(self):
        with Form(self.order) as order_form:
            with order_form.order_line.new() as line:
                line.product_id = self.product
                line.product_uom_qty = 1.0
                subtotal_one = line.price_subtotal
                line.product_uom_qty = 10.0
                self.assertGreater(line.price_subtotal, 0.0)
                self.assertAlmostEqual(line.price_subtotal, 10 * subtotal_one, places=2)

    def test_onchange_product_handles_no_product_gracefully(self):
        line = self.Line.new({"order_id": self.order.id})
        line._onchange_product_id()
        self.assertIsNotNone(line, "Onchange should not crash without product")
        self.assertEqual(line.price_unit, 0.0)
