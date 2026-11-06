"""A transaction has zero or more loads. Each load has one stored parent."""

import importlib.util
import threading
import time
from unittest.mock import patch

from psycopg2 import errors as pg_errors

from odoo import api, fields
from odoo.addons.plasticos_logistics.models.load import (
    _FREIGHT_INTERNAL_WRITE,
    _FREIGHT_INTERNAL_WRITE_TOKEN,
    PlasticosLoad,
)
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.orm.environments import Transaction
from odoo.sql_db import db_connect
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

    def test_sale_order_change_with_linked_loads_is_atomic(self):
        old_order, new_order = self._order(), self._order()
        tx = self._transaction("TX-LOAD-SO-CHANGE", old_order)
        load = self.env["plasticos.load"].create({"sale_order_id": old_order.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            tx.write({"sale_order_id": new_order.id})
        self.assertEqual(tx.sale_order_id, old_order)
        self.assertEqual(load.sale_order_id, old_order)
        self.assertEqual(load.transaction_id, tx)

        without_loads = self._transaction("TX-NO-LOAD-SO-CHANGE", old_order)
        without_loads.write({"sale_order_id": new_order.id})
        self.assertEqual(without_loads.sale_order_id, new_order)

    def test_direct_parent_create_respects_the_join_milestone(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-DIRECT", order)
        load = (
            self.env["plasticos.load"]
            .with_context(plasticos_skip_load_parent_link=True)
            .create({"sale_order_id": order.id, "transaction_id": tx.id})
        )
        tx.invalidate_recordset(["load_ids"])
        self.assertEqual(load.transaction_id, tx)
        self.assertEqual(tx.load_ids, load)
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        before = self.env["plasticos.load"].search_count([])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["plasticos.load"].with_context(plasticos_skip_load_parent_link=True).create(
                {"sale_order_id": order.id, "transaction_id": tx.id}
            )
        self.assertEqual(self.env["plasticos.load"].search_count([]), before)
        self.assertEqual(tx.load_ids, load)

    def _assert_attach_blocks_behind_dispatch(self, label, attach):
        """A draft attach started while dispatch holds the parent lock must not commit."""
        created = {"loads": [], "transactions": [], "orders": [], "partners": [], "parameters": []}

        def cleanup():
            if created["loads"]:

                def reset(env):
                    loads = env["plasticos.load"].browse(created["loads"]).exists()
                    loads.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write(
                        {"state": "draft"}
                    )

                self._commit_in_new_session(reset)
            self._erase_committed(created)

        self.addCleanup(cleanup)

        def build(env):
            buyer = env["res.partner"].create({"name": f"{label} Buyer", "is_company": True, "customer_rank": 1})
            supplier = env["res.partner"].create({"name": f"{label} Supplier", "is_company": True, "supplier_rank": 1})
            order = env["sale.order"].create({"partner_id": buyer.id})
            tx = env["plasticos.transaction"].create(
                {
                    "name": f"TX-{label}",
                    "supplier_id": supplier.id,
                    "buyer_id": buyer.id,
                    "sale_order_id": order.id,
                    "delivery_term": "appointment",
                }
            )
            load = env["plasticos.load"].create({"sale_order_id": order.id})
            load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": "dispatched"})
            tx.with_context(bypass_state_guard=True).write({"state": "supplier_ready"})
            created["partners"].extend([buyer.id, supplier.id])
            created["orders"].append(order.id)
            created["transactions"].append(tx.id)
            created["loads"].append(load.id)
            return order.id, tx.id

        order_id, tx_id = self._commit_in_new_session(build)
        entered = threading.Event()
        release = threading.Event()
        original = PlasticosLoad._loads_blocking_milestone

        def pause_after_guard(load_model, loads, milestone):
            result = original(load_model, loads, milestone)
            if milestone == "dispatched":
                entered.set()
                if not release.wait(8):
                    raise AssertionError("milestone guard barrier timed out")
            return result

        def advance(env):
            env["plasticos.transaction"].browse(tx_id).action_mark_dispatched()
            return True

        attaching = (None, {"committed": False, "error": "load session did not start"})
        sessions = []
        with patch.object(PlasticosLoad, "_loads_blocking_milestone", pause_after_guard):
            try:
                advancing = self._start_session(advance)
                sessions.append(advancing)
                self.assertTrue(entered.wait(8), "milestone guard was not reached")
                attaching = self._start_session(lambda env: attach(env, order_id, tx_id))
                sessions.append(attaching)
                attaching[0].join(0.5)
                self.assertTrue(
                    attaching[0].is_alive(),
                    f"load joined while milestone guard was paused: {attaching[1]}",
                )
            finally:
                release.set()
                self._wait_sessions(sessions)

        if attaching[1].get("result"):
            created["loads"].append(attaching[1]["result"])
        self.assertTrue(advancing[1].get("committed"), advancing[1].get("error"))
        self.assertFalse(attaching[1].get("committed"), attaching[1])
        self.assertTrue(
            any(kind in attaching[1].get("error", "") for kind in ("ValidationError", "SerializationFailure")),
            attaching[1].get("error", ""),
        )
        self.assertEqual(
            self._read_committed("SELECT state FROM plasticos_transaction WHERE id = %s", (tx_id,)),
            [("dispatched",)],
        )
        self.assertEqual(
            self._read_committed(
                "SELECT state FROM plasticos_load WHERE transaction_id = %s ORDER BY state",
                (tx_id,),
            ),
            [("dispatched",)],
        )

    def test_zz_concurrent_late_load_cannot_appear_behind_a_milestone(self):
        def attach(env, order_id, _tx_id):
            return env["plasticos.load"].create({"name": "late-milestone-load", "sale_order_id": order_id}).id

        self._assert_attach_blocks_behind_dispatch("MILESTONE-RACE", attach)

    def test_zz_concurrent_direct_parent_cannot_join_behind_a_milestone(self):
        def attach(env, order_id, tx_id):
            return (
                env["plasticos.load"]
                .with_context(plasticos_skip_load_parent_link=True)
                .create({"name": "late-direct-load", "sale_order_id": order_id, "transaction_id": tx_id})
                .id
            )

        self._assert_attach_blocks_behind_dispatch("DIRECT-RACE", attach)

    def test_zz_stale_snapshot_cannot_advance_over_newly_committed_load(self):
        """A snapshot taken before a committed load must not advance the milestone."""
        created = {"loads": [], "transactions": [], "orders": [], "partners": [], "parameters": []}

        def cleanup():
            def reset(env):
                loads = env["plasticos.load"].browse(created["loads"]).exists()
                loads.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": "draft"})

            self._commit_in_new_session(reset)
            self._erase_committed(created)

        self.addCleanup(cleanup)

        def build(env):
            buyer = env["res.partner"].create({"name": "Snapshot Buyer", "is_company": True, "customer_rank": 1})
            supplier = env["res.partner"].create({"name": "Snapshot Supplier", "is_company": True, "supplier_rank": 1})
            order = env["sale.order"].create({"partner_id": buyer.id})
            tx = env["plasticos.transaction"].create(
                {
                    "name": "TX-STALE-MILESTONE",
                    "supplier_id": supplier.id,
                    "buyer_id": buyer.id,
                    "sale_order_id": order.id,
                    "delivery_term": "appointment",
                }
            )
            load = env["plasticos.load"].create({"sale_order_id": order.id})
            load.with_context(**{_FREIGHT_INTERNAL_WRITE: _FREIGHT_INTERNAL_WRITE_TOKEN}).write({"state": "dispatched"})
            tx.with_context(bypass_state_guard=True).write({"state": "supplier_ready"})
            created["partners"].extend([buyer.id, supplier.id])
            created["orders"].append(order.id)
            created["transactions"].append(tx.id)
            created["loads"].append(load.id)
            return order.id, tx.id

        order_id, tx_id = self._commit_in_new_session(build)
        entered = threading.Event()
        release = threading.Event()

        def stale_advance(env):
            tx = env["plasticos.transaction"].browse(tx_id)
            if tx.state != "supplier_ready":
                raise AssertionError("unexpected initial state")
            entered.set()
            if not release.wait(8):
                raise AssertionError("stale snapshot barrier timed out")
            tx.action_mark_dispatched()
            return True

        session = self._start_session(stale_advance)
        try:
            self.assertTrue(entered.wait(8), "stale transaction never took its snapshot")

            def attach(env):
                return env["plasticos.load"].create({"name": "newly-committed-draft", "sale_order_id": order_id}).id

            created["loads"].append(self._commit_in_new_session(attach))
        finally:
            release.set()
            self._wait_sessions([session])

        self.assertFalse(session[1].get("committed"), session[1])
        self.assertTrue(
            any(token in session[1].get("error", "") for token in ("SerializationFailure", "UserError")),
            session[1].get("error", ""),
        )
        self.assertEqual(
            self._read_committed("SELECT state FROM plasticos_transaction WHERE id = %s", (tx_id,)),
            [("supplier_ready",)],
        )
        self.assertEqual(
            self._read_committed(
                "SELECT state FROM plasticos_load WHERE transaction_id = %s ORDER BY state",
                (tx_id,),
            ),
            [("dispatched",), ("draft",)],
        )

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

    def _real_cursor(self):
        """Open a database connection the test transaction does not wrap.

        ``registry.cursor()`` is patched during tests to a cursor whose
        ``commit()`` only closes a savepoint. Another session cannot see those
        rows, and the test transaction keeps the sequence locks they took.
        """
        cursor = db_connect(self.env.cr.dbname).cursor()
        cursor.execute("SET lock_timeout = '8s'")
        return cursor

    def _commit_in_new_session(self, build):
        """Run ORM writes on a second connection and commit them."""
        cursor = self._real_cursor()
        try:
            env = api.Environment(cursor, self.env.uid, {})
            result = build(env)
            cursor.commit()
            return result
        except Exception:
            cursor.rollback()
            raise
        finally:
            cursor.close()

    def _read_committed(self, query, params):
        cursor = self._real_cursor()
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        finally:
            cursor.rollback()
            cursor.close()

    def _erase_committed(self, ids):
        if not ids:
            return

        def erase(env):
            loads = env["plasticos.load"].browse(ids.get("loads", [])).exists()
            loads.write({"notes": False})
            loads.unlink()
            env["plasticos.transaction"].browse(ids.get("transactions", [])).exists().unlink()
            env["sale.order"].browse(ids.get("orders", [])).exists().unlink()
            env["res.partner"].browse(ids.get("partners", [])).exists().unlink()
            keys = ids.get("parameters", [])
            if keys:
                env["ir.config_parameter"].sudo().search([("key", "in", keys)]).unlink()

        self._commit_in_new_session(erase)

    def _start_session(self, work):
        outcome = {}
        # The test runner holds Registry._lock for the whole suite. A worker
        # that constructs Registry() blocks until the suite ends. Reuse the
        # registry already loaded on this thread.
        registry = self.env.registry

        def run():
            # Odoo retries serialization and deadlock conflicts at the request
            # boundary. Membership bumps make overlapping load inserts conflict;
            # a retry sees the committed sibling and can still commit.
            for attempt in range(1, 6):
                cursor = self._real_cursor()
                try:
                    cursor.transaction = Transaction(registry)
                    env = api.Environment(cursor, self.env.uid, {})
                    outcome["result"] = work(env)
                    cursor.commit()
                    outcome["committed"] = True
                    outcome.pop("error", None)
                    return
                except (pg_errors.SerializationFailure, pg_errors.DeadlockDetected) as exc:
                    cursor.rollback()
                    outcome["committed"] = False
                    outcome["result"] = None
                    outcome["error"] = f"{type(exc).__name__}: {exc}"
                    if attempt == 5:
                        return
                    time.sleep(0.05 * attempt)
                except Exception as exc:
                    cursor.rollback()
                    outcome["committed"] = False
                    outcome["result"] = None
                    outcome["error"] = f"{type(exc).__name__}: {exc}"
                    return
                finally:
                    cursor.close()

        thread = threading.Thread(target=run)
        thread.start()
        return thread, outcome

    def _wait_sessions(self, sessions):
        for thread, _outcome in sessions:
            thread.join(20)
            self.assertFalse(thread.is_alive(), "a database session was still running after 20s")

    def test_two_sessions_commit_distinct_loads_under_one_transaction(self):
        """Two committed sessions can each add a different load to one transaction."""
        created = {"loads": [], "transactions": [], "orders": [], "partners": [], "parameters": []}
        self.addCleanup(lambda: self._erase_committed(created))

        def build(env):
            buyer = env["res.partner"].create({"name": "Concurrent Buyer", "is_company": True, "customer_rank": 1})
            supplier = env["res.partner"].create(
                {"name": "Concurrent Supplier", "is_company": True, "supplier_rank": 1}
            )
            order = env["sale.order"].create({"partner_id": buyer.id})
            transaction = env["plasticos.transaction"].create(
                {
                    "name": "TX-CONCURRENT-LOADS",
                    "supplier_id": supplier.id,
                    "buyer_id": buyer.id,
                    "delivery_term": "appointment",
                    "sale_order_id": order.id,
                }
            )
            created["partners"].extend([buyer.id, supplier.id])
            created["orders"].append(order.id)
            created["transactions"].append(transaction.id)
            return order.id, transaction.id

        order_id, transaction_id = self._commit_in_new_session(build)

        def add_load(marker):
            def work(env):
                load = env["plasticos.load"].create({"name": marker, "sale_order_id": order_id, "notes": marker})
                return load.id

            return work

        first = self._start_session(add_load("session-load-a"))
        second = self._start_session(add_load("session-load-b"))
        self._wait_sessions([first, second])
        for outcome in (first[1], second[1]):
            if outcome.get("result"):
                created["loads"].append(outcome["result"])
        self.assertTrue(first[1].get("committed"), first[1].get("error"))
        self.assertTrue(second[1].get("committed"), second[1].get("error"))

        rows = self._read_committed(
            """
            SELECT id, transaction_id, notes
              FROM plasticos_load
             WHERE id IN %s
             ORDER BY notes
            """,
            (tuple(created["loads"]),),
        )
        self.assertEqual(
            [(row[1], row[2]) for row in rows],
            [(transaction_id, "session-load-a"), (transaction_id, "session-load-b")],
        )
        parents = self._read_committed(
            "SELECT COUNT(*) FROM plasticos_load WHERE transaction_id = %s",
            (transaction_id,),
        )
        self.assertEqual(parents[0][0], 2)

    def test_two_sessions_cannot_both_commit_competing_load_ownership(self):
        """One load accepts one committed parent. The losing session rolls back completely.

        Under repeatable read the loser can receive SerializationFailure when it
        locks a row the winner already updated. That failure commits nothing:
        no parent and no partial evidence row.
        """
        created = {"loads": [], "transactions": [], "orders": [], "partners": [], "parameters": []}
        self.addCleanup(lambda: self._erase_committed(created))

        def build(env):
            buyer = env["res.partner"].create({"name": "Ownership Buyer", "is_company": True, "customer_rank": 1})
            supplier = env["res.partner"].create({"name": "Ownership Supplier", "is_company": True, "supplier_rank": 1})
            order = env["sale.order"].create({"partner_id": buyer.id})
            values = {
                "supplier_id": supplier.id,
                "buyer_id": buyer.id,
                "delivery_term": "appointment",
                "sale_order_id": order.id,
            }
            first_tx = env["plasticos.transaction"].create({**values, "name": "TX-OWNERSHIP-A"})
            second_tx = env["plasticos.transaction"].create({**values, "name": "TX-OWNERSHIP-B"})
            load = (
                env["plasticos.load"]
                .with_context(plasticos_skip_load_parent_link=True)
                .create({"sale_order_id": order.id})
            )
            created["partners"].extend([buyer.id, supplier.id])
            created["orders"].append(order.id)
            created["transactions"].extend([first_tx.id, second_tx.id])
            created["loads"].append(load.id)
            return load.id, first_tx.id, second_tx.id

        load_id, first_tx_id, second_tx_id = self._commit_in_new_session(build)
        created["parameters"].extend(
            [f"plasticos.concurrency.{load_id}.owner-a", f"plasticos.concurrency.{load_id}.owner-b"]
        )
        unlinked = self._read_committed("SELECT transaction_id FROM plasticos_load WHERE id = %s", (load_id,))
        self.assertIsNone(unlinked[0][0])

        def assign(transaction_id, marker):
            def work(env):
                env["ir.config_parameter"].sudo().create(
                    {"key": f"plasticos.concurrency.{load_id}.{marker}", "value": marker}
                )
                env["plasticos.load"].browse(load_id).write({"transaction_id": transaction_id, "notes": marker})
                return marker

            return work

        first = self._start_session(assign(first_tx_id, "owner-a"))
        second = self._start_session(assign(second_tx_id, "owner-b"))
        self._wait_sessions([first, second])
        outcomes = [first[1], second[1]]
        committed = [item for item in outcomes if item.get("committed")]
        rolled_back = [item for item in outcomes if not item.get("committed")]
        self.assertEqual(len(committed), 1, outcomes)
        self.assertEqual(len(rolled_back), 1, outcomes)
        loser = rolled_back[0].get("error", "")
        self.assertTrue(
            "ValidationError" in loser or "SerializationFailure" in loser,
            loser,
        )
        winner = committed[0]["result"]

        rows = self._read_committed(
            "SELECT transaction_id, sale_order_id, notes FROM plasticos_load WHERE id = %s",
            (load_id,),
        )
        parent_id, _sale_order_id, notes = rows[0]
        self.assertIn(parent_id, {first_tx_id, second_tx_id})
        self.assertEqual(notes, winner)
        self.assertEqual(parent_id, first_tx_id if winner == "owner-a" else second_tx_id)
        evidence = self._read_committed(
            "SELECT key, value FROM ir_config_parameter WHERE key LIKE %s ORDER BY key",
            (f"plasticos.concurrency.{load_id}.%",),
        )
        self.assertEqual(evidence, [(f"plasticos.concurrency.{load_id}.{winner}", winner)])
        owner_counts = self._read_committed(
            """
            SELECT transaction_id, COUNT(*)
              FROM plasticos_load
             WHERE id = %s
             GROUP BY transaction_id
            """,
            (load_id,),
        )
        self.assertEqual(owner_counts, [(parent_id, 1)])

    def test_reconcile_links_two_sale_orders_in_one_call(self):
        """Each sale order with one eligible transaction links only its own unlinked loads."""
        first_order, second_order = self._order(), self._order()
        first_load = self.env["plasticos.load"].create({"sale_order_id": first_order.id})
        second_load = self.env["plasticos.load"].create({"sale_order_id": second_order.id})
        first_tx = self.env["plasticos.transaction"].create(
            {"name": "TX-LOAD-BATCH-1", "sale_order_id": first_order.id, "buyer_id": self.buyer.id}
        )
        second_tx = self.env["plasticos.transaction"].create(
            {"name": "TX-LOAD-BATCH-2", "sale_order_id": second_order.id, "buyer_id": self.buyer.id}
        )
        self.assertFalse(first_load.transaction_id)
        self.assertFalse(second_load.transaction_id)
        (first_tx | second_tx).write({"supplier_id": self.supplier.id})
        self.assertEqual(first_load.transaction_id, first_tx)
        self.assertEqual(second_load.transaction_id, second_tx)

    def test_create_does_not_link_an_unlinked_load_on_another_sale_order(self):
        order = self._order()
        tx = self._transaction("TX-LOAD-OWN", order)
        other = self.env["plasticos.load"].create({"sale_order_id": self._order().id})
        created = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(created.transaction_id, tx)
        self.assertFalse(other.transaction_id)

    def test_reconcile_leaves_a_load_unlinked_when_the_milestone_fails(self):
        order = self._order()
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        tx = self._transaction("TX-LOAD-MILE-SKIP")
        tx.with_context(bypass_state_guard=True).write({"state": "delivered"})
        tx.write({"sale_order_id": order.id})
        self.assertFalse(load.transaction_id)
        self.assertFalse(tx.load_ids)
