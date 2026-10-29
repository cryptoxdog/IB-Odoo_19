"""One sales-dashboard row per transaction, including a deal with several loads."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalesDashboardLoadCardinality(TransactionCase):
    def test_three_loads_do_not_multiply_the_deal(self):
        buyer = self.env["res.partner"].create({"name": "Dash Buyer", "customer_rank": 1})
        supplier = self.env["res.partner"].create({"name": "Dash Supplier", "supplier_rank": 1})
        order = self.env["sale.order"].create({"partner_id": buyer.id})
        tx = self.env["plasticos.transaction"].create(
            {
                "name": "TX-DASH-LOADS",
                "supplier_id": supplier.id,
                "buyer_id": buyer.id,
                "sale_order_id": order.id,
            }
        )
        early = "2026-01-01 08:00:00"
        later = "2026-01-03 08:00:00"
        alpha = self.env["res.partner"].create({"name": "Alpha Carrier", "is_company": True})
        beta = self.env["res.partner"].create({"name": "Beta Carrier", "is_company": True})
        loads = self.env["plasticos.load"].create([{"sale_order_id": order.id} for _index in range(3)])
        loads[0].write({"carrier_id": beta.id, "pickup_datetime": later})
        loads[1].write({"carrier_id": alpha.id, "pickup_datetime": early})
        loads[2].write({"pickup_datetime": later})
        self.env.flush_all()
        dashboard = self.env["plasticos.sales.dashboard"]
        dashboard.init()
        rows = dashboard.search([("transaction_id", "=", tx.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.load_count, 3)
        self.assertFalse(rows.load_id)
        self.assertFalse(rows.load_state)
        self.assertEqual(rows.carrier_name, "Alpha Carrier, Beta Carrier")
        self.assertEqual(str(rows.pickup_datetime), early)
        self.assertEqual(rows.revenue_total, tx.revenue_total)
        self.assertEqual(rows.gross_margin, tx.gross_margin)
        action = rows.action_view_load()
        self.assertEqual(action["tag"], "display_notification")
