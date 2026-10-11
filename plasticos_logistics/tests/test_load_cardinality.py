"""One load belongs to one transaction, and close chatter uses that link."""

from odoo.addons.plasticos_logistics.models.load import (
    _FREIGHT_INTERNAL_WRITE,
    _FREIGHT_INTERNAL_WRITE_TOKEN,
)
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadCardinality(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Load Parent", "is_company": True})
        cls.supplier = cls.env["res.partner"].create(
            {"name": "Load Supplier", "is_company": True, "parent_id": parent.id, "supplier_rank": 1}
        )
        cls.buyer = cls.env["res.partner"].create(
            {"name": "Load Buyer", "is_company": True, "parent_id": parent.id, "customer_rank": 1}
        )

    def _transaction(self, name, sale_order=None):
        values = {
            "name": name,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "delivery_term": "appointment",
        }
        if sale_order:
            values["sale_order_id"] = sale_order.id
        return self.env["plasticos.transaction"].create(values)

    def test_create_links_the_sale_order_transaction_once(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self._transaction("TX-LOAD-LINK", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(tx.load_id, load)
        self.assertEqual(load.transaction_id, tx)

    def test_close_posts_one_chatter_message(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx = self._transaction("TX-LOAD-CLOSE", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": "closed"})
        closed = tx.message_ids.filtered(lambda message: "Logistics closed." in (message.body or ""))
        self.assertEqual(len(closed), 1)

    def test_delivery_term_override_reads_the_linked_transaction(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        self._transaction("TX-LOAD-TERM", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id, "delivery_term": "fcfs"})
        self.assertTrue(load.delivery_term_overridden)

    def test_a_second_transaction_cannot_take_the_same_load(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        self._transaction("TX-LOAD-ONE", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        other = self._transaction("TX-LOAD-TWO")
        with self.assertRaises(Exception), self.env.cr.savepoint():
            other.load_id = load
            self.env.flush_all()
