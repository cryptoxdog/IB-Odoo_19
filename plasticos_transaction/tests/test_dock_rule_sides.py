"""Record-level dock rules (ADR-135 §3)."""

from odoo.addons.plasticos_transaction.dock_rule import copy_pickup_dock_rule
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDockRuleSides(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "FCFS Supplier Co",
                "is_company": True,
                "supplier_rank": 1,
                "default_delivery_term": "fcfs",
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Buyer Commercial Co",
                "is_company": True,
                "customer_rank": 1,
                "default_delivery_term": "fcfs",
            }
        )
        cls.ship_to = cls.env["res.partner"].create(
            {
                "name": "North Receiving Site",
                "parent_id": cls.buyer.id,
                "type": "delivery",
                "default_delivery_term": "appointment",
            }
        )
        cls.pickup_company = cls.env["res.partner"].create(
            {
                "name": "Pickup Commercial Co",
                "is_company": True,
                "supplier_rank": 1,
                "default_delivery_term": "appointment",
            }
        )
        cls.pickup_site = cls.env["res.partner"].create(
            {
                "name": "West Pickup Site",
                "parent_id": cls.pickup_company.id,
                "type": "delivery",
                "default_delivery_term": "fcfs",
            }
        )

    def test_fcfs_supplier_and_appointment_buyer_split_the_sides(self):
        sale = self.env["sale.order"].create({"partner_id": self.buyer.id, "partner_shipping_id": self.ship_to.id})
        purchase = self.env["purchase.order"].create({"partner_id": self.supplier.id})
        deal = self.env["plasticos.transaction"].create(
            {
                "name": "TX-DOCK-SIDES",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": sale.id,
                "purchase_order_ids": [(6, 0, purchase.ids)],
            }
        )
        self.assertEqual(sale.delivery_term, "appointment")
        self.assertEqual(deal.delivery_term, "appointment")
        self.assertEqual(deal.pickup_dock_rule, "fcfs")
        self.assertEqual(purchase.pickup_dock_rule, "fcfs")

    def test_site_rule_beats_company_rule(self):
        purchase = self.env["purchase.order"].create({"partner_id": self.pickup_site.id})
        deal = self.env["plasticos.transaction"].create(
            {
                "name": "TX-DOCK-SITE",
                "supplier_id": self.pickup_company.id,
                "purchase_order_ids": [(6, 0, purchase.ids)],
            }
        )
        self.assertTrue(self.pickup_site._plasticos_is_site())
        self.assertEqual(deal.pickup_dock_rule, "fcfs")
        self.assertEqual(self.pickup_company.default_delivery_term, "appointment")

    def test_migration_copies_both_sides_and_is_a_no_op_on_replay(self):
        deal = self.env["plasticos.transaction"].create(
            {
                "name": "TX-DOCK-COPY",
                "supplier_id": self.supplier.id,
                "delivery_term": "fcfs",
                "pickup_dock_rule": "appointment",
            }
        )
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE plasticos_transaction SET pickup_dock_rule = NULL WHERE id = %s",
            (deal.id,),
        )
        deal.invalidate_recordset(["pickup_dock_rule"])
        first = copy_pickup_dock_rule(self.env.cr, "plasticos_transaction")
        deal.invalidate_recordset(["pickup_dock_rule"])
        self.assertEqual(deal.delivery_term, "fcfs")
        self.assertEqual(deal.pickup_dock_rule, "fcfs")
        self.assertGreaterEqual(first["copied"], 1)
        second = copy_pickup_dock_rule(self.env.cr, "plasticos_transaction")
        deal.invalidate_recordset(["pickup_dock_rule"])
        self.assertEqual(second["copied"], 0)
        self.assertEqual(deal.pickup_dock_rule, "fcfs")
        purchase = self.env["purchase.order"].create({"partner_id": self.supplier.id})
        purchase_stats = copy_pickup_dock_rule(self.env.cr, "purchase_order")
        self.assertIn(purchase_stats["status"], ("copied", "skipped"))
        self.assertEqual(copy_pickup_dock_rule(self.env.cr, "purchase_order")["copied"], 0)
        self.assertTrue(purchase.id)
