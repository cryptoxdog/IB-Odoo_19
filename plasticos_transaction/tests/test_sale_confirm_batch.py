"""Sale confirmation and the CSV line importer create their records in one batch."""

from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


def _counting(model_cls, method_name, calls):
    real = getattr(model_cls, method_name)

    def wrapped(self, *args, **kwargs):
        calls.append(args[0] if args else kwargs)
        return real(self, *args, **kwargs)

    return patch.object(model_cls, method_name, wrapped)


@tagged("post_install", "-at_install", "transaction", "sale")
class TestSaleConfirmBatch(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.buyer = cls.env["res.partner"].create({"name": "Confirm Batch Buyer", "is_company": True})
        cls.product = cls.env["product.product"].create({"name": "Confirm Batch Goods", "type": "consu"})
        cls.tx_cls = type(cls.env["plasticos.transaction"])

    def _order(self, origin=None):
        vals = {
            "partner_id": self.buyer.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 10, "price_unit": 1.0})],
        }
        if origin:
            vals["origin"] = origin
        return self.env["sale.order"].create(vals)

    def test_confirming_two_orders_creates_their_transactions_in_one_call(self):
        orders = self._order() | self._order()
        creates = []
        with _counting(self.tx_cls, "create", creates):
            orders.action_confirm()
        self.assertEqual(len(creates), 1, creates)
        self.assertTrue(all(order.transaction_id for order in orders))
        self.assertEqual(len(orders.mapped("transaction_id")), 2)
        for order in orders:
            self.assertEqual(order.transaction_id.sale_order_id, order)
            self.assertEqual(order.transaction_id.buyer_id, self.buyer)

    def test_two_live_orders_sharing_an_origin_keep_distinct_transaction_names(self):
        orders = self._order(origin="WS-SHARED-1") | self._order(origin="WS-SHARED-1")
        orders.action_confirm()
        names = orders.mapped("transaction_id.name")
        self.assertEqual(len(set(names)), 2, names)
        self.assertIn("WS-SHARED-1", names)
        self.assertTrue(any(name.startswith("WS-SHARED-1-") for name in names), names)

    def test_csv_line_import_creates_lines_in_one_batch(self):
        tx = self.env["plasticos.transaction"].create({"name": "TX-CSV-BATCH-1"})
        service = self.env["plasticos.transaction.import.service"]
        rows = [
            {"DetailID": "1", "GradeID": "G1", "InvoiceDesc": "First", "SWeight": "100", "PWeight": "100"},
            {"DetailID": "2", "GradeID": "G2", "InvoiceDesc": "Second", "SWeight": "200", "PWeight": "200"},
        ]
        creates = []
        with _counting(type(self.env["plasticos.transaction.line"]), "create", creates):
            count = service._create_transaction_lines(tx, rows)
        self.assertEqual(count, 2)
        self.assertEqual(len(creates), 1, creates)
        self.assertEqual(self.env["plasticos.transaction.line"].search_count([("transaction_id", "=", tx.id)]), 2)
