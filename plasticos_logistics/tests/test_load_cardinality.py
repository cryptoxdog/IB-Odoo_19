"""A transaction has zero or more loads. Each load has one stored parent."""

import importlib.util

from odoo import fields
from odoo.addons.plasticos_logistics.models.load import (
    _FREIGHT_INTERNAL_WRITE,
    _FREIGHT_INTERNAL_WRITE_TOKEN,
)
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _migration(filename):
    path = get_module_path("plasticos_logistics") + "/migrations/19.0.1.14.6/" + filename
    spec = importlib.util.spec_from_file_location(f"load_parent_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def _transaction(self, name, sale_order=None, **extra):
        values = {
            "name": name,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "delivery_term": "appointment",
        }
        if sale_order:
            values["sale_order_id"] = sale_order.id
        values.update(extra)
        return self.env["plasticos.transaction"].create(values)

    def _order(self):
        return self.env["sale.order"].create({"partner_id": self.buyer.id})

    def test_create_links_the_sale_order_transaction_once(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-LINK", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(load.transaction_id, tx)
        self.assertEqual(tx.load_ids, load)
        self.assertEqual(tx.load_count, 1)

    def test_zero_loads_open_an_empty_set(self):
        tx = self._transaction("TX-LOAD-EMPTY")
        action = tx.action_view_loads()
        self.assertFalse(tx.load_ids)
        self.assertEqual(action["domain"], [("transaction_id", "=", tx.id)])
        self.assertNotIn("res_id", action)

    def test_two_loads_stay_on_the_same_transaction(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-MANY", order)
        first = self.env["plasticos.load"].create({"sale_order_id": order.id})
        second = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(set(tx.load_ids.ids), {first.id, second.id})
        action = tx.action_view_loads()
        self.assertNotIn("res_id", action)
        self.assertEqual(action["domain"], [("transaction_id", "=", tx.id)])

    def test_a_load_without_an_eligible_transaction_stays_unlinked(self):
        load = self.env["plasticos.load"].create({"sale_order_id": self._order().id})
        self.assertFalse(load.transaction_id)

    def test_ambiguous_sale_order_does_not_pick_a_transaction(self):
        order = self._order()
        self._transaction("TX-LOAD-AMB-1", order)
        self._transaction("TX-LOAD-AMB-2", order)
        before = self.env["plasticos.load"].search_count([])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(self.env["plasticos.load"].search_count([]), before)

    def test_close_posts_one_chatter_message(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-CLOSE", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": "closed"})
        closed = tx.message_ids.filtered(lambda message: "Logistics closed." in (message.body or ""))
        self.assertEqual(len(closed), 1)

    def test_delivery_term_override_reads_the_linked_transaction(self):
        order = self._order()
        self._transaction("TX-LOAD-TERM", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id, "delivery_term": "fcfs"})
        self.assertTrue(load.delivery_term_overridden)

    def test_a_second_transaction_cannot_take_the_same_load(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-ONE", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        other = self._transaction("TX-LOAD-TWO")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = other
        self.assertEqual(load.transaction_id, tx)

    def test_missing_supplier_or_buyer_refuses_the_link(self):
        tx = self.env["plasticos.transaction"].create({"name": "TX-LOAD-PARTIAL", "supplier_id": self.supplier.id})
        load = self.env["plasticos.load"].create({})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = tx
        self.assertFalse(load.transaction_id)

    def test_cross_company_link_is_refused(self):
        company_b = self.env["res.company"].create({"name": "Load Cardinality Other"})
        self.env.user.write({"company_ids": [(4, company_b.id)]})
        order_a = self._order()
        order_b = (
            self.env["sale.order"]
            .with_company(company_b)
            .create({"partner_id": self.buyer.id, "company_id": company_b.id})
        )
        tx = self._transaction("TX-LOAD-CO", order_a)
        load = self.env["plasticos.load"].create({"sale_order_id": order_b.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = tx
        self.assertFalse(load.transaction_id)

    def test_dispatched_or_evidence_bearing_link_cannot_be_cleared(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-LOCK", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": "dispatched"})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = False
        self.assertEqual(load.transaction_id, tx)

        draft = self.env["plasticos.load"].create({"sale_order_id": order.id, "transaction_id": tx.id})
        draft.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"rate_confirmed_at": fields.Datetime.now()}
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            draft.transaction_id = False
        self.assertEqual(draft.transaction_id, tx)

    def test_parent_migration_copies_a_null_parent_and_refuses_a_disagreement(self):
        pre = _migration("pre-migrate.py")
        self.env.cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (pre._MIGRATION_MARKER,))
        order = self._order()
        tx = self._transaction("TX-LOAD-MIG", order)
        other = self._transaction("TX-LOAD-MIG-OTHER")
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        cr = self.env.cr
        cr.execute("ALTER TABLE plasticos_transaction ADD COLUMN IF NOT EXISTS load_id integer")
        cr.execute(
            """
            UPDATE plasticos_transaction AS t
               SET load_id = l.id
              FROM plasticos_load AS l
             WHERE l.transaction_id = t.id
               AND t.load_id IS NULL
               AND NOT EXISTS (
                    SELECT 1 FROM plasticos_load other
                     WHERE other.transaction_id = t.id
                       AND other.id <> l.id
               )
            """
        )
        cr.execute("UPDATE plasticos_load SET transaction_id = NULL WHERE id = %s", (load.id,))
        cr.execute("UPDATE plasticos_transaction SET load_id = %s WHERE id = %s", (load.id, tx.id))
        pre.migrate(cr, "19.0.1.14.5")
        cr.execute("SELECT transaction_id FROM plasticos_load WHERE id = %s", (load.id,))
        self.assertEqual(cr.fetchone()[0], tx.id)
        pre.migrate(cr, "19.0.1.14.5")
        cr.execute("SELECT transaction_id FROM plasticos_load WHERE id = %s", (load.id,))
        self.assertEqual(cr.fetchone()[0], tx.id)

        with self.env.cr.savepoint():
            cr.execute("UPDATE plasticos_load SET transaction_id = %s WHERE id = %s", (other.id, load.id))
            with self.assertRaises(RuntimeError):
                pre.migrate(cr, "19.0.1.14.5")
            cr.execute("SELECT transaction_id FROM plasticos_load WHERE id = %s", (load.id,))
            self.assertEqual(cr.fetchone()[0], other.id)

    def _set_state(self, load, state):
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": state})

    def test_delayed_eligibility_links_the_only_transaction(self):
        order = self._order()
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertFalse(load.transaction_id)
        tx = self._transaction("TX-LOAD-LATER", order)
        self.assertEqual(load.transaction_id, tx)

    def test_a_second_eligible_transaction_does_not_move_an_existing_load(self):
        order = self._order()
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        first = self._transaction("TX-LOAD-FIRST", order)
        second = self._transaction("TX-LOAD-SECOND", order)
        self.assertEqual(load.transaction_id, first)
        self.assertNotEqual(load.transaction_id, second)

    def test_mismatched_sale_order_is_refused_and_the_load_stays_unlinked(self):
        load = self.env["plasticos.load"].create({"sale_order_id": self._order().id})
        other = self._transaction("TX-LOAD-OTHER-SO", self._order())
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = other
        self.assertFalse(load.transaction_id)

    def test_ordinary_clear_and_reassign_are_refused(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-KEEP", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        other = self._transaction("TX-LOAD-MOVE", order)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = False
        self.assertEqual(load.transaction_id, tx)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = other
        self.assertEqual(load.transaction_id, tx)
        load.action_correct_draft_parent(other, "Operator corrected the draft parent.")
        self.assertEqual(load.transaction_id, other)
        noted = load.message_ids.filtered(lambda message: "Draft transaction link corrected." in (message.body or ""))
        self.assertTrue(noted)

    def test_duplicate_drops_parent_dates_and_evidence(self):
        order = self._order()
        self._transaction("TX-LOAD-COPY", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        when = fields.Datetime.now()
        self._set_state(load, "delivered")
        load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
            {"delivered_at": when, "dispatched_at": when}
        )
        duplicate = load.copy()
        self.assertFalse(duplicate.transaction_id)
        self.assertFalse(duplicate.delivered_at)
        self.assertFalse(duplicate.dispatched_at)
        self.assertEqual(duplicate.state, "draft")
        self.assertEqual(load.transaction_id.sale_order_id, order)

    def test_protected_load_and_transaction_cannot_be_removed(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-DELETE", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self._set_state(load, "dispatched")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            load.unlink()
        self.assertTrue(load.exists())
        with self.assertRaises(UserError), self.env.cr.savepoint():
            tx.unlink()
        self.assertTrue(tx.exists())

    def test_a_draft_load_cannot_join_a_delivered_transaction(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-LATE", order)
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        before = self.env["plasticos.load"].search_count([])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(self.env["plasticos.load"].search_count([]), before)
        self.assertFalse(tx.load_ids)

    def test_transaction_milestones_wait_for_every_load(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-MILE", order)
        first = self.env["plasticos.load"].create({"sale_order_id": order.id})
        second = self.env["plasticos.load"].create({"sale_order_id": order.id})
        tx.with_context(bypass_state_guard=True).write({"state": "supplier_ready"})
        self._set_state(first, "dispatched")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            tx.action_mark_dispatched()
        self.assertEqual(tx.state, "supplier_ready")
        self._set_state(second, "dispatched")
        tx.action_mark_dispatched()
        self.assertEqual(tx.state, "dispatched")
        self._set_state(first, "picked_up")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            tx.action_mark_in_transit()
        self.assertEqual(tx.state, "dispatched")
        self._set_state(second, "picked_up")
        tx.action_mark_in_transit()
        self._set_state(first, "delivered")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            tx.action_mark_delivered()
        self.assertEqual(tx.state, "in_transit")
        self._set_state(second, "delivered")
        tx.action_mark_delivered()
        self.assertEqual(tx.state, "delivered")

    def test_a_transaction_without_loads_can_still_be_dispatched(self):
        tx = self._transaction("TX-LOAD-PO")
        tx.with_context(bypass_state_guard=True).write({"state": "supplier_ready"})
        tx.action_mark_dispatched()
        self.assertEqual(tx.state, "dispatched")

    def test_completed_parent_migration_does_not_restore_a_cleared_link(self):
        pre = _migration("pre-migrate.py")
        post = _migration("post-migrate.py")
        self.env.cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (pre._MIGRATION_MARKER,))
        order = self._order()
        tx = self._transaction("TX-LOAD-MARKER", order)
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        cr = self.env.cr
        cr.execute("ALTER TABLE plasticos_transaction ADD COLUMN IF NOT EXISTS load_id integer")
        cr.execute("UPDATE plasticos_load SET transaction_id = NULL WHERE id = %s", (load.id,))
        cr.execute("UPDATE plasticos_transaction SET load_id = %s WHERE id = %s", (load.id, tx.id))
        post.migrate(cr, "19.0.1.14.5")
        cr.execute("SELECT transaction_id FROM plasticos_load WHERE id = %s", (load.id,))
        self.assertEqual(cr.fetchone()[0], tx.id)
        cr.execute("UPDATE plasticos_load SET transaction_id = NULL WHERE id = %s", (load.id,))
        pre.migrate(cr, "19.0.1.14.5")
        post.migrate(cr, "19.0.1.14.5")
        cr.execute("SELECT transaction_id FROM plasticos_load WHERE id = %s", (load.id,))
        self.assertIsNone(cr.fetchone()[0])

    def test_a_second_session_blocks_on_a_held_row_lock(self):
        company_id = self.env.company.id
        self.env.cr.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", (company_id,))
        other = self.env.registry.cursor()
        try:
            other.execute("SET lock_timeout = '300ms'")
            with self.assertRaises(Exception):
                other.execute("SELECT id FROM res_company WHERE id = %s FOR UPDATE", (company_id,))
            other.rollback()
        finally:
            other.close()
        self.assertTrue(self.env.company.exists())
