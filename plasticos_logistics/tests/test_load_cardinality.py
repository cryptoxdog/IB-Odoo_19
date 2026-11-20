"""A transaction has zero or more loads. Each load has one stored parent."""

import importlib.util
import re
import threading
import time
from datetime import timedelta
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
            "pickup_dock_rule": "appointment",
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
        # S6: a database that already ran 14.6 keeps the old column with values for rows this
        # test does not own. The replay reads the whole table, so the legacy input is limited
        # to the rows this test writes below (rolled back with the test).
        cr.execute("UPDATE plasticos_transaction SET load_id = NULL WHERE load_id IS NOT NULL")
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
        # S6: a database that already ran 14.6 keeps the old column with values for rows this
        # test does not own. The replay reads the whole table, so the legacy input is limited
        # to the rows this test writes below (rolled back with the test).
        cr.execute("UPDATE plasticos_transaction SET load_id = NULL WHERE load_id IS NOT NULL")
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


def _migration_1420(filename):
    path = get_module_path("plasticos_logistics") + "/migrations/19.0.1.14.21/" + filename
    spec = importlib.util.spec_from_file_location(f"load_company_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestLoadSourceCompanyAndPhysicalEvents(TransactionCase):
    """S2 witnesses: V01 company and exact parent, V03 manual freight, V04 release guard, V10 actual clocks.

    BRS-EXP-01-R003, BRS-EXP-04-R001/R003, BRS-EXP-08-R001/R008, BRS-EXP-10-R004/R006/R007/R008.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        # The acknowledgment escalation is owned by an Operations Manager in the load's company.
        cls.ops_manager = cls.env["res.users"].create(
            {
                "name": "s2.ops.manager",
                "login": "s2.ops.manager",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("plasticos_security_base.group_operations_manager").id,
                        ],
                    )
                ],
            }
        )
        cls.supplier = cls.env["res.partner"].create(
            {"name": "S2 Supplier", "is_company": True, "supplier_rank": 1, "street": "1 Mill Rd", "city": "Houston"}
        )
        cls.terminal = cls.env["res.partner"].create(
            {"name": "S2 Rail Ramp", "is_company": True, "street": "9 Ramp Way", "city": "Dallas"}
        )
        cls.buyer = cls.env["res.partner"].create({"name": "S2 Buyer", "is_company": True, "customer_rank": 1})
        cls.carrier = cls.env["res.partner"].create(
            {"name": "S2 Carrier", "is_company": True, "supplier_rank": 1, "email": "dispatch@carrier.example"}
        )

    # ── helpers ──────────────────────────────────────────────────────────

    def _buyerless_load(self, **extra):
        values = {
            "company_id": self.company.id,
            "pickup_partner_id": self.supplier.id,
            "delivery_partner_id": self.terminal.id,
            "reference_weight": 42000,
            "carrier_id": self.carrier.id,
            "rate_currency_id": self.currency.id,
        }
        values.update(extra)
        return self.env["plasticos.load"].create(values)

    def _ready(self, load):
        load._transition("awaiting_ready")
        load.action_confirm_ready()
        return load

    def _manual_rate(self, load, rate=950.0):
        self._ready(load)
        load.action_confirm_rate(rate)
        return load

    def _attach(self, load, name="bol.pdf"):
        return self.env["ir.attachment"].create(
            {"name": name, "raw": b"%PDF-1.4 actual", "res_model": "plasticos.load", "res_id": load.id}
        )

    def _purchase_transaction(self, company=None, **extra):
        po = self.env["purchase.order"].create(
            {"partner_id": self.supplier.id, "company_id": (company or self.company).id}
        )
        values = {"name": "TX-S2-PO", "supplier_id": self.supplier.id, "purchase_order_ids": [(6, 0, po.ids)]}
        values.update(extra)
        return self.env["plasticos.transaction"].create(values)

    def _logistics_user(self, login):
        groups = self.env.ref("base.group_user") | self.env.ref("plasticos_security_base.group_logistics")
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
                "group_ids": [(6, 0, groups.ids)],
            }
        )

    # ── V01: source company and exact parent (BRS-EXP-08-R001/R008) ──────

    def test_sale_order_load_takes_its_sale_order_company(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        self.assertEqual(load.company_id, order.company_id)

    def test_named_company_must_match_the_sale_order(self):
        other = self.env["res.company"].create({"name": "S2 Other Co"})
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["plasticos.load"].create({"sale_order_id": order.id, "company_id": other.id})

    def test_user_must_name_the_company_of_a_buyerless_load(self):
        """The user's current company is never taken as the source of a new load."""
        user = self._logistics_user("s2.nocompany")
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["plasticos.load"].with_user(user).create({"pickup_partner_id": self.supplier.id})
        load = self.env["plasticos.load"].with_user(user).create({"company_id": self.company.id})
        self.assertEqual(load.company_id, self.company)

    def test_company_is_immutable_once_the_load_leaves_draft(self):
        other = self.env["res.company"].create({"name": "S2 Locked Co"})
        load = self._buyerless_load()
        load._transition("awaiting_ready")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.write({"company_id": other.id})
        self.assertEqual(load.company_id, self.company)

    def test_buyerless_load_joins_a_purchase_backed_transaction(self):
        """BRS-EXP-01-R003 / AC-EXP-08-001: no buyer, no sale order, no dummy counterpart."""
        load = self._buyerless_load()
        tx = self._purchase_transaction()
        partners = self.env["res.partner"].search_count([])
        orders = self.env["sale.order"].search_count([])
        result = self.env["plasticos.load"].action_bind_exact_transaction_load(
            tx.id, load.id, {"route": "purchase"}, "op-s2-po"
        )
        self.assertEqual(result, {"status": "applied", "record_id": load.id})
        self.assertEqual(load.transaction_id, tx)
        self.assertFalse(tx.buyer_id)
        self.assertEqual(self.env["res.partner"].search_count([]), partners)
        self.assertEqual(self.env["sale.order"].search_count([]), orders)
        replay = self.env["plasticos.load"].action_bind_exact_transaction_load(
            tx.id, load.id, {"route": "purchase"}, "op-s2-po"
        )
        self.assertEqual(replay["status"], "already_applied")

    def test_bind_refuses_a_route_the_records_do_not_support(self):
        load = self._buyerless_load()
        tx = self._purchase_transaction()
        result = self.env["plasticos.load"].action_bind_exact_transaction_load(
            tx.id, load.id, {"route": "sale"}, "op-s2-wrong-route"
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(load.transaction_id)

    def test_buyerless_load_cannot_join_a_purchase_order_of_another_company(self):
        other = self.env["res.company"].create({"name": "S2 PO Co"})
        load = self._buyerless_load()
        tx = self._purchase_transaction(company=other)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = tx
        self.assertFalse(load.transaction_id)

    def test_buyerless_load_cannot_join_a_transaction_without_purchase_orders(self):
        load = self._buyerless_load()
        tx = self.env["plasticos.transaction"].create({"name": "TX-S2-BARE", "supplier_id": self.supplier.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.transaction_id = tx
        self.assertFalse(load.transaction_id)

    def test_sale_backed_route_still_requires_the_real_buyer(self):
        """AC-EXP-08-008: ordinary sale dispatch still rejects an absent buyer."""
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self.env["plasticos.load"].create({"sale_order_id": order.id})
        tx = self.env["plasticos.transaction"].create(
            {"name": "TX-S2-NOBUYER", "sale_order_id": order.id, "supplier_id": self.supplier.id}
        )
        result = self.env["plasticos.load"].action_bind_exact_transaction_load(
            tx.id, load.id, {"route": "sale"}, "op-s2-nobuyer"
        )
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(load.transaction_id)

    # ── V03: manual freight versus repeat-rate reuse (BRS-EXP-10-R006) ───

    def test_buyerless_manual_rate_uses_the_manual_context(self):
        from odoo.addons.plasticos_logistics.services.freight_context import FREIGHT_CONTEXT_MANUAL_VERSION

        load = self._manual_rate(self._buyerless_load())
        self.assertEqual(load.state, "rate_confirmed")
        self.assertEqual(load.rate_resolution_method, "manual")
        self.assertEqual(load.freight_context_version, FREIGHT_CONTEXT_MANUAL_VERSION)
        self.assertFalse(load.transaction_id)

    def test_same_as_last_abstains_for_a_buyerless_load(self):
        self._manual_rate(self._buyerless_load())
        fresh = self._ready(self._buyerless_load(carrier_id=False))
        fresh.action_resolve_freight()
        self.assertEqual(fresh.sal_decision, "not_eligible")
        self.assertEqual(fresh.sal_miss_reason, "missing_lane_identity")
        self.assertFalse(fresh.rate_confirmed_at)
        self.assertFalse(fresh.sal_source_load_id)

    def test_manual_context_cannot_confirm_a_same_as_last_rate(self):
        from odoo.addons.plasticos_logistics.services.freight_context import (
            FREIGHT_CONTEXT_MANUAL_VERSION,
            build_manual_freight_context,
        )

        load = self._ready(self._buyerless_load())
        context = build_manual_freight_context(load)
        with self.assertRaises(ValidationError):
            load._confirm_freight_rate(
                rate=900.0,
                carrier=self.carrier,
                currency=self.currency,
                resolution_method="sal",
                context_fingerprint=context.fingerprint,
                sal_source_load=load,
                context_version=FREIGHT_CONTEXT_MANUAL_VERSION,
            )

    def test_changed_lane_withholds_release_of_a_manual_rate(self):
        load = self._manual_rate(self._buyerless_load())
        now = fields.Datetime.now()
        load.delivery_partner_id.street = "10 Moved Ramp Way"
        with self.assertRaises(UserError):
            load.action_schedule(now, now)
        self.assertEqual(load.state, "rate_confirmed")

    # ── V04: one release guard on every new-instruction path ─────────────

    def _scheduled(self):
        load = self._manual_rate(self._buyerless_load())
        now = fields.Datetime.now()
        load.action_schedule(now, now)
        return load

    def test_owner_hold_blocks_every_release_path(self):
        """A downstream owner's hold (e.g. a rolled booking) stops each route to a new instruction."""
        load = self._scheduled()
        dispatch = self.env["plasticos.dispatch"].create({"load_id": load.id})
        hold = patch.object(PlasticosLoad, "_physical_release_errors", lambda self, kind: ["Booking rolled."])
        with hold:
            verdict = self.env["plasticos.load"].assert_can_release_physical_operation(load.id, "dispatch")
            self.assertEqual(verdict["status"], "blocked")
            for attempt in (
                load.action_dispatch,
                lambda: load._transition("dispatched"),
                load.action_send_dispatch_packet,
                load.action_send_bol_pickup,
                load.action_send_dispatch_direct,
                lambda: dispatch.action_transition("dispatched"),
            ):
                with self.subTest(attempt=attempt), self.assertRaises(UserError), self.env.cr.savepoint():
                    attempt()
        self.assertEqual(load.state, "scheduled")
        self.assertEqual(dispatch.state, "quoted")
        self.assertEqual(
            self.env["plasticos.load"].assert_can_release_physical_operation(load.id, "dispatch"),
            {"status": "applied", "record_id": load.id},
        )

    def test_release_check_reports_a_stale_context_token(self):
        load = self._scheduled()
        verdict = self.env["plasticos.load"].assert_can_release_physical_operation(load.id, "dispatch", "old-token")
        self.assertEqual(verdict["status"], "stale")
        unknown = self.env["plasticos.load"].assert_can_release_physical_operation(load.id, "sail")
        self.assertEqual(unknown["status"], "not_available")

    def test_hold_does_not_block_recording_what_already_happened(self):
        """A hold withholds new release; it cannot erase evidence that the truck already moved."""
        load = self._scheduled()
        load.action_dispatch()
        evidence = self._attach(load, "signed-bol.pdf")
        picked_at = fields.Datetime.now() - timedelta(hours=2)
        with patch.object(PlasticosLoad, "_physical_release_errors", lambda self, kind: ["Booking rolled."]):
            result = load.action_record_actual_event("pickup", picked_at, evidence)
            load._transition("picked_up")
        self.assertEqual(result["status"], "applied")
        self.assertEqual(load.actual_pickup_at, picked_at.replace(microsecond=0))
        self.assertEqual(load.state, "picked_up")

    def test_dispatch_state_cannot_be_written_around_the_guard(self):
        load = self._scheduled()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["plasticos.dispatch"].create({"load_id": load.id, "state": "dispatched"})
        dispatch = self.env["plasticos.dispatch"].create({"load_id": load.id})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            dispatch.write({"state": "dispatched"})
        dispatch.action_transition("dispatched")
        self.assertEqual(dispatch.state, "dispatched")

    def test_acknowledgment_job_escalates_without_resending_the_packet(self):
        load = self._scheduled()
        load.action_dispatch()
        load.write({"dispatch_sent": fields.Datetime.now() - timedelta(hours=5)})
        with patch.object(
            PlasticosLoad, "action_send_dispatch_direct", side_effect=AssertionError("blind resend")
        ) as resend:
            # S6: scoped to this test's load; other dispatched loads in the database are not its subject.
            self.env["plasticos.load"].with_context(
                linda_load_sweep_ids=load.ids
            )._cron_check_dispatch_acknowledgments()
        resend.assert_not_called()
        summary = f"URGENT: No carrier acknowledgment for {load.name}"
        self.assertEqual(
            self.env["mail.activity"].search_count([("res_id", "=", load.id), ("summary", "=", summary)]), 1
        )

    def test_acknowledgment_job_reaches_loads_beyond_one_page_once_each(self):
        """S6 D9: escalated loads stay eligible, so a fixed oldest-first page must not starve newer loads."""
        loads = self.env["plasticos.load"].create(
            [
                {
                    "company_id": self.company.id,
                    "pickup_partner_id": self.supplier.id,
                    "delivery_partner_id": self.terminal.id,
                    "carrier_id": self.carrier.id,
                }
                for _index in range(101)
            ]
        )
        oldest = fields.Datetime.now() - timedelta(hours=30)
        for offset, load in enumerate(loads):
            # Legacy dispatched rows: the state and clock are written directly, oldest first.
            self.env.cr.execute(
                "UPDATE plasticos_load SET state = 'dispatched', dispatch_sent = %s, dispatch_acknowledged = NULL "
                "WHERE id = %s",
                (oldest + timedelta(minutes=offset), load.id),
            )
        loads.invalidate_recordset()
        cron = self.env["plasticos.load"].with_context(linda_load_sweep_ids=loads.ids)

        def escalated():
            activities = self.env["mail.activity"].search(
                [
                    ("res_model", "=", "plasticos.load"),
                    ("res_id", "in", loads.ids),
                    ("summary", "ilike", "URGENT: No carrier acknowledgment"),
                ]
            )
            return activities.mapped("res_id")

        with patch.object(PlasticosLoad, "action_send_dispatch_direct", side_effect=AssertionError("blind resend")):
            cron._cron_check_dispatch_acknowledgments()
            self.assertEqual(len(escalated()), 100, "one run is bounded to one page")
            cron._cron_check_dispatch_acknowledgments()
            self.assertEqual(sorted(escalated()), sorted(loads.ids), "the next run reaches the newest load, once each")
            cron._cron_check_dispatch_acknowledgments()
        self.assertEqual(len(escalated()), 101, "a load is never escalated twice on one day")

    def test_acknowledgment_job_dedupes_in_the_user_timezone(self):
        """S6 D9 review N1: a cron user whose date differs from UTC still escalates a load once."""
        load = self._scheduled()
        load.action_dispatch()
        load.write({"dispatch_sent": fields.Datetime.now() - timedelta(hours=5)})
        # A zone whose calendar date differs from UTC's right now (UTC+14 late in the UTC day, UTC-12 early).
        tz = "Pacific/Kiritimati" if fields.Datetime.now().hour >= 12 else "Etc/GMT+12"
        cron = self.env["plasticos.load"].with_context(tz=tz, linda_load_sweep_ids=load.ids)
        self.assertNotEqual(fields.Date.context_today(cron), fields.Date.today(), tz)
        with patch.object(PlasticosLoad, "action_send_dispatch_direct", side_effect=AssertionError("blind resend")):
            cron._cron_check_dispatch_acknowledgments()
            cron._cron_check_dispatch_acknowledgments()
        summary = f"URGENT: No carrier acknowledgment for {load.name}"
        self.assertEqual(
            self.env["mail.activity"].search_count([("res_id", "=", load.id), ("summary", "=", summary)]), 1
        )

    # ── Manager escalation routing (operator decision: managers only, never silent) ──

    def _unacknowledged(self, **extra):
        load = self._buyerless_load(**extra)
        # A legacy dispatched row: the state and clock are written directly.
        self.env.cr.execute(
            "UPDATE plasticos_load SET state = 'dispatched', dispatch_sent = %s, dispatch_acknowledged = NULL "
            "WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=5), load.id),
        )
        load.invalidate_recordset()
        return load

    def _ack_activities(self, load):
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", "plasticos.load"),
                ("res_id", "=", load.id),
                ("summary", "=", f"URGENT: No carrier acknowledgment for {load.name}"),
            ]
        )

    def _unrouted_notes(self, load):
        load.invalidate_recordset(["message_ids"])
        return load.message_ids.filtered(lambda message: "Not routed:" in (message.body or ""))

    def test_acknowledgment_escalation_goes_to_a_manager_never_the_salesperson(self):
        sales = self.env["res.users"].create(
            {
                "name": "s2.ack.sales",
                "login": "s2.ack.sales",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        transaction = self.env["plasticos.transaction"].create(
            {
                "name": "TX-S2-ACK-ROUTE",
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "sale_order_id": order.id,
                "user_id": sales.id,
            }
        )
        load = self.env["plasticos.load"].create(
            {
                "sale_order_id": order.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.buyer.id,
                "carrier_id": self.carrier.id,
            }
        )
        self.assertEqual(load.transaction_id, transaction)
        self.assertEqual(load.transaction_id.user_id, sales)
        self.env.cr.execute(
            "UPDATE plasticos_load SET state = 'dispatched', dispatch_sent = %s, dispatch_acknowledged = NULL "
            "WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=5), load.id),
        )
        load.invalidate_recordset()
        seen = []
        users = type(self.env["res.users"])
        original = users._plasticos_escalation_manager

        def recorder(self, group_xmlid, company=None):
            seen.append((group_xmlid, company))
            return original(self, group_xmlid, company)

        cron = self.env["plasticos.load"].with_context(linda_load_sweep_ids=load.ids)
        with patch.object(users, "_plasticos_escalation_manager", recorder):
            cron._cron_check_dispatch_acknowledgments()
        self.assertEqual(seen, [("plasticos_security_base.group_operations_manager", load.company_id)])
        activities = self._ack_activities(load)
        self.assertEqual(len(activities), 1)
        self.assertTrue(activities.user_id.has_group("plasticos_security_base.group_operations_manager"))
        cron_user = self.env.ref("plasticos_base.user_system_cron")
        self.assertNotIn(activities.user_id, sales | cron_user | self.env.user)
        self.assertFalse(self._unrouted_notes(load))

    def test_acknowledgment_escalation_without_a_manager_is_logged_and_noted_once(self):
        load = self._unacknowledged()
        users = type(self.env["res.users"])
        cron = self.env["plasticos.load"].with_context(linda_load_sweep_ids=load.ids)
        with patch.object(
            users, "_plasticos_escalation_manager", lambda self, group_xmlid, company=None: self.browse()
        ):
            with self.assertLogs("odoo.addons.plasticos_base.models.res_users", level="ERROR") as captured:
                cron._cron_check_dispatch_acknowledgments()
            with self.assertLogs("odoo.addons.plasticos_base.models.res_users", level="ERROR"):
                cron._cron_check_dispatch_acknowledgments()
        self.assertTrue(any("Not routed: carrier acknowledgment escalation." in line for line in captured.output))
        self.assertEqual(len(self._unrouted_notes(load)), 1)
        self.assertFalse(self._ack_activities(load), "neither the cron user nor a salesperson takes it")

    def test_acknowledgment_escalation_is_scoped_to_the_load_company(self):
        """A manager of another company never owns the load's escalation."""
        other = self.env["res.company"].create({"name": "S2 Escalation Other Company"})
        load = self._unacknowledged(company_id=other.id, rate_currency_id=other.currency_id.id)
        cron = self.env["plasticos.load"].with_context(linda_load_sweep_ids=load.ids)
        with self.assertLogs("odoo.addons.plasticos_base.models.res_users", level="ERROR"):
            cron._cron_check_dispatch_acknowledgments()
        self.assertFalse(self._ack_activities(load))
        self.assertEqual(len(self._unrouted_notes(load)), 1)
        group = self.env.ref("plasticos_security_base.group_operations_manager")
        local = self.env["res.users"].create(
            {
                "name": "s2.ack.other.manager",
                "login": "s2.ack.other.manager",
                "company_id": other.id,
                "company_ids": [(6, 0, [other.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id, group.id])],
            }
        )
        cron._cron_check_dispatch_acknowledgments()
        self.assertEqual(self._ack_activities(load).user_id, local)

    def test_sla_breach_is_assigned_to_a_manager_once(self):
        load = self._buyerless_load()
        self.env.cr.execute(
            "UPDATE plasticos_load SET state = 'awaiting_ready', entered_state_at = %s, sla_breached = FALSE "
            "WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=60), load.id),
        )
        load.invalidate_recordset()
        summary = f"ESCALATION: SLA breach [WARNING] on {load.name}"
        self.env["plasticos.load"]._cron_escalation_check()
        self.assertTrue(load.sla_breached)
        activities = self.env["mail.activity"].search([("res_id", "=", load.id), ("summary", "=", summary)])
        self.assertEqual(len(activities), 1)
        self.assertTrue(activities.user_id.has_group("plasticos_security_base.group_operations_manager"))
        self.assertNotIn(activities.user_id, self.env.ref("plasticos_base.user_system_cron") | self.env.user)
        self.env["plasticos.load"]._cron_escalation_check()
        load._escalate_sla_breach("warning", 61.0, 48)
        self.assertEqual(
            self.env["mail.activity"].search_count([("res_id", "=", load.id), ("summary", "=", summary)]), 1
        )

    def test_sla_breach_without_a_manager_is_logged_and_noted_once(self):
        load = self._buyerless_load()
        users = type(self.env["res.users"])
        with patch.object(
            users, "_plasticos_escalation_manager", lambda self, group_xmlid, company=None: self.browse()
        ):
            with self.assertLogs("odoo.addons.plasticos_base.models.res_users", level="ERROR") as captured:
                load._escalate_sla_breach("critical", 100.0, 48)
            with self.assertLogs("odoo.addons.plasticos_base.models.res_users", level="ERROR"):
                load._escalate_sla_breach("critical", 100.0, 48)
        self.assertTrue(any("Not routed: SLA breach critical escalation." in line for line in captured.output))
        self.assertEqual(len(self._unrouted_notes(load)), 1)
        self.assertFalse(
            self.env["mail.activity"].search([("res_id", "=", load.id), ("summary", "ilike", "SLA breach")])
        )

    # ── V10: actual event clocks (BRS-EXP-04-R001/R003, BRS-EXP-10-R007) ──

    def test_state_changes_never_fill_actual_clocks(self):
        load = self._scheduled()
        load.action_dispatch()
        load._transition("picked_up")
        load._transition("delivered")
        self.assertTrue(load.delivered_at)
        self.assertFalse(load.actual_pickup_at)
        self.assertFalse(load.actual_delivery_at)

    def test_actual_pickup_needs_evidence_attached_to_this_load(self):
        load = self._buyerless_load()
        other = self._buyerless_load()
        foreign = self._attach(other, "other-bol.pdf")
        when = fields.Datetime.now() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            load.action_record_actual_event("pickup", when, foreign)
        with self.assertRaises(UserError):
            load.action_record_actual_event("pickup", when, self.env["ir.attachment"])
        self.assertFalse(load.actual_pickup_at)

    def test_delayed_entry_keeps_the_actual_time_and_replays_once(self):
        load = self._buyerless_load()
        evidence = self._attach(load)
        when = fields.Datetime.now() - timedelta(days=3)
        first = load.action_record_actual_event("pickup", when, evidence)
        replay = load.action_record_actual_event("pickup", when, evidence)
        self.assertEqual((first["status"], replay["status"]), ("applied", "already_applied"))
        self.assertEqual(load.actual_pickup_at, when.replace(microsecond=0))
        self.assertEqual(load.pickup_evidence_attachment_id, evidence)
        events = self.env["plasticos.freight.event"].search(
            [("load_id", "=", load.id), ("event_type", "=", "actual_pickup_recorded")]
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events.facts["evidence_attachment_id"], evidence.id)
        self.assertEqual(events.company_id, load.company_id)

    def test_correction_needs_a_reason_and_keeps_the_first_event(self):
        load = self._buyerless_load()
        evidence = self._attach(load)
        first_time = fields.Datetime.now() - timedelta(days=2)
        load.action_record_actual_event("pickup", first_time, evidence)
        corrected = first_time + timedelta(hours=1)
        with self.assertRaises(UserError):
            load.action_record_actual_event("pickup", corrected, evidence)
        load.action_record_actual_event("pickup", corrected, evidence, reason="Scale ticket shows the later time.")
        self.assertEqual(load.actual_pickup_at, corrected.replace(microsecond=0))
        types = self.env["plasticos.freight.event"].search([("load_id", "=", load.id)]).mapped("event_type")
        self.assertIn("actual_pickup_recorded", types)
        self.assertIn("actual_event_corrected", types)

    def test_actual_clocks_refuse_future_time_order_and_direct_writes(self):
        load = self._buyerless_load()
        evidence = self._attach(load)
        now = fields.Datetime.now()
        with self.assertRaises(ValidationError):
            load.action_record_actual_event("pickup", now + timedelta(days=1), evidence)
        load.action_record_actual_event("pickup", now - timedelta(hours=1), evidence)
        with self.assertRaises(ValidationError):
            load.action_record_actual_event("delivery", now - timedelta(hours=5), evidence)
        with self.assertRaises(UserError):
            load.write({"actual_delivery_at": now})
        with self.assertRaises(UserError):
            self._buyerless_load(actual_pickup_at=now)

    def test_delivered_to_port_without_a_buyer_fact(self):
        """AC-EXP-04-003 / AC-EXP-10-007: physical delivery evidence with buyer allocation pending."""
        load = self._buyerless_load()
        evidence = self._attach(load, "ramp-receipt.pdf")
        moves = self.env["account.move"].search_count([])
        load.action_record_actual_event("delivery", fields.Datetime.now() - timedelta(hours=1), evidence)
        self.assertTrue(load.actual_delivery_at)
        self.assertFalse(load.transaction_id)
        self.assertEqual(self.env["account.move"].search_count([]), moves)

    # ── 19.0.1.14.21 migration (company census; first shipped as 19.0.1.14.20) ───────────────────────────

    def test_company_census_repairs_one_source_and_refuses_none(self):
        pre = _migration_1420("pre-migrate.py")
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        repairable = self.env["plasticos.load"].create({"sale_order_id": order.id})
        orphan = self.env["plasticos.load"].create({"pickup_partner_id": self.supplier.id})
        self.assertFalse(orphan.company_id)
        self.env.cr.execute("UPDATE plasticos_load SET company_id = NULL WHERE id = %s", (repairable.id,))
        repairable.invalidate_recordset(["company_id"])
        repairs, refusals = pre.census(self.env.cr)
        self.assertIn((repairable.id, order.company_id.id, "sale_order"), repairs)
        self.assertIn((orphan.id, "no_source_company", []), refusals)
        with self.assertRaises(RuntimeError):
            pre.migrate(self.env.cr, "19.0.1.14.19")
        repairable.invalidate_recordset(["company_id"])
        self.assertFalse(repairable.company_id, "a refused census changes no row")
        orphan.unlink()
        pre.migrate(self.env.cr, "19.0.1.14.19")
        repairable.invalidate_recordset(["company_id"])
        self.assertEqual(repairable.company_id, order.company_id)
        self.assertEqual(pre.census(self.env.cr), ([], []))

    def test_post_migration_rerun_is_a_no_op(self):
        post = _migration_1420("post-migrate.py")
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        self.env["plasticos.load"].create({"sale_order_id": order.id})
        journeys = self.env["plasticos.iso.journey"].search_count([])
        post.migrate(self.env.cr, "19.0.1.14.19")
        post.migrate(self.env.cr, "19.0.1.14.19")
        self.assertEqual(self.env["plasticos.iso.journey"].search_count([]), journeys)
        self.assertEqual(post.discrepancies(self.env.cr), [])

    # ── Verification round 1 (C01-REAUTH-2): D1, D3 and refinements ──────

    def test_user_cannot_clear_the_company_of_a_load(self):
        """D1: a cleared company would hide the load behind the global rule for every user."""
        user = self._logistics_user("s2.clearco")
        load = self.env["plasticos.load"].with_user(user).create({"company_id": self.company.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            load.with_user(user).write({"company_id": False})
        load.invalidate_recordset(["company_id"])
        self.assertEqual(load.company_id, self.company)
        as_superuser = self.env["plasticos.load"].sudo().browse(load.id)
        as_superuser.write({"company_id": False})
        self.assertFalse(as_superuser.company_id, "only the superuser may clear a company")

    def test_actual_event_replay_ignores_sub_second_precision(self):
        load = self._buyerless_load()
        evidence = self._attach(load)
        when = fields.Datetime.now() - timedelta(hours=3)
        first = load.action_record_actual_event("pickup", when.replace(microsecond=250000), evidence)
        replay = load.action_record_actual_event("pickup", when.replace(microsecond=750000), evidence)
        self.assertEqual((first["status"], replay["status"]), ("applied", "already_applied"))
        self.assertEqual(load.actual_pickup_at, when.replace(microsecond=0))
        corrected = self.env["plasticos.freight.event"].search_count(
            [("load_id", "=", load.id), ("event_type", "=", "actual_event_corrected")]
        )
        self.assertEqual(corrected, 0)

    def _null_company(self, load):
        # Pending ORM writes reach the table before the raw census reads it.
        self.env.flush_all()
        self.env.cr.execute("UPDATE plasticos_load SET company_id = NULL WHERE id = %s", (load.id,))
        load.invalidate_recordset(["company_id"])

    def test_company_census_repairs_from_a_purchase_backed_parent(self):
        pre = _migration_1420("pre-migrate.py")
        load = self._buyerless_load()
        tx = self._purchase_transaction()
        load.transaction_id = tx
        self._null_company(load)
        repairs, refusals = pre.census(self.env.cr)
        self.assertIn((load.id, self.company.id, "transaction_purchase_order"), repairs)
        self.assertFalse([row for row in refusals if row[0] == load.id])

    def test_company_census_refuses_conflicting_and_disagreeing_sources(self):
        pre = _migration_1420("pre-migrate.py")
        other = self.env["res.company"].create({"name": "S2 Census Other"})
        order_a = self.env["sale.order"].create({"partner_id": self.buyer.id})
        order_b = (
            self.env["sale.order"].with_company(other).create({"partner_id": self.buyer.id, "company_id": other.id})
        )
        tx_b = self.env["plasticos.transaction"].create({"name": "TX-S2-CENSUS-B", "sale_order_id": order_b.id})
        conflicting = self.env["plasticos.load"].create({"sale_order_id": order_a.id})
        self.env.cr.execute("UPDATE plasticos_load SET transaction_id = %s WHERE id = %s", (tx_b.id, conflicting.id))
        disagreeing = self.env["plasticos.load"].create({"sale_order_id": order_a.id})
        self.env.cr.execute("UPDATE plasticos_load SET company_id = %s WHERE id = %s", (other.id, disagreeing.id))
        _repairs, refusals = pre.census(self.env.cr)
        reasons = {load_id: reason for load_id, reason, _detail in refusals}
        self.assertEqual(reasons.get(conflicting.id), "conflicting_source_companies")
        self.assertEqual(reasons.get(disagreeing.id), "company_disagrees_with_source")
        message = pre.refusal_message(refusals)
        self.assertIn("correct the wrong link", message)
        self.assertIn("correct one of them", message)

    def test_company_census_reads_the_pre_14_6_parent_column(self):
        """Old-column path: before 14.6 the parent was plasticos_transaction.load_id."""
        pre = _migration_1420("pre-migrate.py")
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        tx_one = self.env["plasticos.transaction"].create({"name": "TX-S2-OLD-1", "sale_order_id": order.id})
        tx_two = self.env["plasticos.transaction"].create({"name": "TX-S2-OLD-2", "sale_order_id": order.id})
        repairable = self._buyerless_load()
        doubled = self._buyerless_load()
        cr = self.env.cr
        cr.execute("ALTER TABLE plasticos_transaction ADD COLUMN IF NOT EXISTS load_id integer")
        cr.execute("UPDATE plasticos_transaction SET load_id = %s WHERE id = %s", (repairable.id, tx_one.id))
        cr.execute("UPDATE plasticos_transaction SET load_id = %s WHERE id = %s", (doubled.id, tx_two.id))
        tx_three = self.env["plasticos.transaction"].create({"name": "TX-S2-OLD-3", "sale_order_id": order.id})
        cr.execute("UPDATE plasticos_transaction SET load_id = %s WHERE id = %s", (doubled.id, tx_three.id))
        self._null_company(repairable)
        real_has_column = pre.has_column

        def old_schema(cursor, table, column):
            if (table, column) == ("plasticos_load", "transaction_id"):
                return False
            return real_has_column(cursor, table, column)

        with patch.object(pre, "has_column", old_schema):
            self.assertEqual(pre._parent_link_sql(cr), pre._PARENT_FROM_TRANSACTION)
            repairs, refusals = pre.census(cr)
        self.assertIn((repairable.id, order.company_id.id, "transaction_sale_order"), repairs)
        self.assertIn((doubled.id, "several_parent_transactions", sorted([tx_two.id, tx_three.id])), refusals)

    def test_refusal_message_names_the_remedy_and_caps_the_listing(self):
        pre = _migration_1420("pre-migrate.py")
        refusals = [(load_id, "no_source_company", []) for load_id in range(1, 31)]
        refusals.append((99, "several_parent_transactions", [7, 8]))
        message = pre.refusal_message(refusals, cap=5)
        self.assertIn("no_source_company (30 load(s))", message)
        self.assertIn("attach its sale order", message)
        self.assertIn("delete it if it is a stray draft", message)
        self.assertIn("and 25 more", message)
        self.assertNotIn(" 6,", message)
        self.assertIn("keep exactly one parent transaction", message)

    # ── C01-REAUTH-4 (a): carrier documents name the load's own company ──

    _CARRIER_REPORTS = (
        "plasticos_logistics.report_delivery_order",
        "plasticos_logistics.report_bol_pickup",
        "plasticos_logistics.report_bol_delivery",
    )

    def _render(self, report_ref, load):
        html, _kind = self.env["ir.actions.report"]._render_qweb_html(report_ref, load.ids)
        return html.decode() if isinstance(html, bytes) else str(html)

    def _assert_issuer_block(self, html, company):
        """The template's own issuer block (bold name, then street), not the layout header."""
        import re

        from markupsafe import escape

        pattern = (
            r"<strong[^>]*>\s*"
            + re.escape(str(escape(company.name)))
            + r"\s*</strong>\s*<br\s*/?>\s*"
            + re.escape(str(escape(company.street or "")))
        )
        self.assertRegex(html, pattern)

    def test_carrier_documents_name_the_company_of_a_buyerless_load(self):
        # A second company makes the issuer come from the load, never env.company.
        other = self.env["res.company"].create({"name": "S2 Buyerless Issuer Co", "street": "7 Yard Rd"})
        load = self._buyerless_load(company_id=other.id)
        load.transaction_id = self._purchase_transaction(company=other)
        self.assertFalse(load.sale_order_id)
        self.assertNotEqual(self.env.company, other)
        for report_ref in self._CARRIER_REPORTS:
            with self.subTest(report_ref):
                self._assert_issuer_block(self._render(report_ref, load), other)

    def test_carrier_documents_keep_the_sale_order_company_of_a_sale_backed_load(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self.env["plasticos.load"].create(
            {"sale_order_id": order.id, "pickup_partner_id": self.supplier.id, "delivery_partner_id": self.terminal.id}
        )
        self.assertEqual(load.company_id, order.company_id)
        for report_ref in self._CARRIER_REPORTS:
            with self.subTest(report_ref):
                self._assert_issuer_block(self._render(report_ref, load), order.company_id)


@tagged("post_install", "-at_install")
class TestCarrierComposerSendTimeRelease(TransactionCase):
    """S4 D2 / V06 witness: opening a carrier composer is not the release authorization.

    The guard is read again inside ``mail.compose.message._action_send_mail``. A lane
    change made while the composer is open must refuse the send and queue no mail
    (Codex 4545252969, BRS-EXP-10-R004/R008).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # D5: carrier mail is sent from the load's own company and nothing stands in for it.
        cls.company.email = "dispatch@s4-composer-company.example"
        cls.supplier = cls.env["res.partner"].create(
            {"name": "S4 Composer Mill", "is_company": True, "supplier_rank": 1, "street": "2 Mill Rd"}
        )
        cls.terminal = cls.env["res.partner"].create(
            {"name": "S4 Composer Ramp", "is_company": True, "street": "3 Ramp Way", "city": "Dallas"}
        )
        cls.carrier = cls.env["res.partner"].create(
            {"name": "S4 Composer Carrier", "is_company": True, "email": "packet@s4-composer.example"}
        )

    def _scheduled_load(self):
        load = self.env["plasticos.load"].create(
            {
                "company_id": self.company.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.terminal.id,
                "reference_weight": 42000,
                "carrier_id": self.carrier.id,
                "rate_currency_id": self.company.currency_id.id,
            }
        )
        load._transition("awaiting_ready")
        load.action_confirm_ready()
        load.action_confirm_rate(950.0)
        now = fields.Datetime.now()
        load.action_schedule(now, now)
        return load

    def _open(self, action):
        return self.env["mail.compose.message"].with_context(**action["context"]).create({})

    def _outgoing_for(self, load):
        return self.env["mail.message"].search_count(
            [("model", "=", "plasticos.load"), ("res_id", "=", load.id), ("message_type", "=", "email_outgoing")]
        ) + self.env["mail.mail"].search_count([("model", "=", "plasticos.load"), ("res_id", "=", load.id)])

    def test_lane_change_while_the_composer_is_open_refuses_the_send(self):
        load = self._scheduled_load()
        composer = self._open(load.action_send_dispatch_packet())
        self.assertEqual(composer._plasticos_load_release_operation(), "dispatch_packet")
        before = self._outgoing_for(load)
        messages_before = len(load.message_ids)
        # The governed context changes after the composer opened.
        load.delivery_partner_id.street = "11 Moved Ramp Way"
        with self.assertRaises(UserError), self.env.cr.savepoint():
            composer.action_send_mail()
        self.assertEqual(self._outgoing_for(load), before, "no dispatch mail is queued")
        self.assertEqual(len(load.message_ids), messages_before, "no message is posted")

    def test_each_carrier_document_composer_rechecks_at_send(self):
        load = self._scheduled_load()
        windows = (
            ("action_send_delivery_order", load.action_send_delivery_order()),
            ("action_send_bol_pickup", load.action_send_bol_pickup()),
            ("action_send_bol_delivery", load.action_send_bol_delivery()),
        )
        for name, window in windows:
            with self.subTest(action=name):
                composer = self._open(window)
                self.assertEqual(composer._plasticos_load_release_operation(), "carrier_document")
                with patch.object(PlasticosLoad, "_physical_release_errors", lambda self, kind: ["Booking rolled."]):
                    with self.assertRaises(UserError), self.env.cr.savepoint():
                        composer.action_send_mail()

    def test_a_carrier_composer_cannot_be_scheduled_past_the_check(self):
        load = self._scheduled_load()
        composer = self._open(load.action_send_dispatch_packet())
        composer.scheduled_date = fields.Datetime.now() + timedelta(hours=1)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            composer.action_send_mail()
        self.assertFalse(
            self.env["mail.scheduled.message"].search([("model", "=", "plasticos.load"), ("res_id", "=", load.id)])
        )

    def test_only_a_confirmed_packet_send_starts_the_acknowledgement_clock(self):
        """Codex 4545894603: the composer path stamps dispatch_sent on transport success, not on queueing."""
        load = self._scheduled_load()
        load.action_dispatch()
        self.assertFalse(load.dispatch_sent)
        other = self._scheduled_load()
        # A mail whose marker names another load never stamps this one.
        forged = self.env["mail.mail"].create(
            {
                "model": "plasticos.load",
                "res_id": load.id,
                "email_to": self.carrier.email,
                "subject": "not a packet",
                "body_html": "<p>forged</p>",
                "headers": repr({"X-Plasticos-Release": f"dispatch_packet:{other.id}"}),
            }
        )
        server_class = type(self.env["ir.mail_server"])
        sink = (
            patch.object(server_class, "_disable_send", lambda *args: False),
            patch.object(server_class, "_connect__", lambda *args, **kwargs: None),
            patch.object(server_class, "send_email", lambda server, message, *a, **k: message["Message-Id"]),
        )
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=forged.ids)
        self.assertEqual(forged.state, "sent", "the forged mail really went out, so the checks below are not vacuous")
        load.invalidate_recordset()
        other.invalidate_recordset()
        self.assertFalse(load.dispatch_sent, "a foreign marker does not stamp this load")
        self.assertFalse(other.dispatch_sent, "a marker on another load's mail does not stamp it either")
        self._open(load.action_send_dispatch_packet()).action_send_mail()
        packet_mails = self.env["mail.mail"].search(
            [("model", "=", "plasticos.load"), ("res_id", "=", load.id), ("headers", "ilike", "X-Plasticos-Release")]
        )
        self.assertTrue(packet_mails, "the packet mail is tagged for the acknowledgement clock")
        self.assertFalse(load.dispatch_sent, "queueing is not sending")
        to_carrier = packet_mails.filtered(
            lambda mail: (
                self.carrier.email in (mail.email_to or "") or self.carrier.email in mail.recipient_ids.mapped("email")
            )
        )
        self.assertTrue(
            to_carrier, "the composer emails the carrier: " + "; ".join(map(self._mail_diagnosis, packet_mails))
        )
        packet_ids = packet_mails.ids
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=packet_ids)
        for mail in self.env["mail.mail"].browse(packet_ids):
            if mail.exists():
                self.assertEqual(mail.state, "sent", f"{self._mail_diagnosis(mail)} headers={mail.headers}")
        load.invalidate_recordset()
        self.assertTrue(load.dispatch_sent, "a confirmed send stamps the clock")
        stamped = load.dispatch_sent
        # A second confirmed packet never moves the first clock.
        self._open(load.action_send_dispatch_packet()).action_send_mail()
        load.invalidate_recordset()
        self.assertEqual(load.dispatch_sent, stamped)

    def _sink(self):
        server_class = type(self.env["ir.mail_server"])
        return (
            patch.object(server_class, "_disable_send", lambda *args: False),
            patch.object(server_class, "_connect__", lambda *args, **kwargs: None),
            patch.object(server_class, "send_email", lambda server, message, *a, **k: message["Message-Id"]),
        )

    def _last_load_mail(self, load):
        return self.env["mail.mail"].search(
            [("model", "=", "plasticos.load"), ("res_id", "=", load.id)], order="id desc", limit=1
        )

    @staticmethod
    def _mail_diagnosis(mail):
        return (
            f"state={mail.state} failure={mail.failure_type} {mail.failure_reason} from={mail.email_from} "
            f"to={mail.email_to} partners={mail.recipient_ids.mapped('email')}"
        )

    def test_a_company_without_its_own_sender_never_confirms_a_packet(self):
        """D5 fails closed: no sender address means no confirmed send and no ACK clock."""
        load = self._scheduled_load()
        load.action_dispatch()
        self.company.email = False
        sink = self._sink()
        with sink[0], sink[1], sink[2]:
            self.assertFalse(load.action_send_dispatch_direct())
        self.assertFalse(
            self.env["mail.mail"].search(
                [("model", "=", "plasticos.load"), ("res_id", "=", load.id), ("state", "=", "sent")]
            ),
            "no load mail reached sent",
        )
        self.assertFalse(load.dispatch_sent, "an unsent packet never starts the clock")
        # A malformed address is no sender either.
        self.company.email = "not-an-address"
        with sink[0], sink[1], sink[2]:
            self.assertFalse(load.action_send_dispatch_direct())
        self.assertFalse(load.dispatch_sent)

    def test_a_composer_for_a_company_without_its_own_sender_refuses_the_send(self):
        """D5 fails closed on the composer path too: a UserError naming the company, and no mail."""
        load = self._scheduled_load()
        load.action_dispatch()
        composer = self._open(load.action_send_dispatch_packet())
        self.company.email = False
        before = self._outgoing_for(load)
        with self.assertRaisesRegex(UserError, re.escape(self.company.name)), self.env.cr.savepoint():
            composer.action_send_mail()
        self.assertEqual(self._outgoing_for(load), before, "no carrier mail is queued")
        self.assertFalse(
            self.env["mail.mail"].search(
                [("model", "=", "plasticos.load"), ("res_id", "=", load.id), ("state", "=", "sent")]
            )
        )
        self.assertFalse(load.dispatch_sent)

    def _packet_mail(self, load, **values):
        return self.env["mail.mail"].create(
            {
                "model": "plasticos.load",
                "res_id": load.id,
                "subject": "packet",
                "body_html": "<p>packet</p>",
                "headers": repr({"X-Plasticos-Release": f"dispatch_packet:{load.id}"}),
                **values,
            }
        )

    def test_a_follower_copy_does_not_start_the_carrier_clock(self):
        """Review R1: only the copy addressed to the load's own carrier proves the instruction left."""
        load = self._scheduled_load()
        load.action_dispatch()
        follower = self.env["res.partner"].create({"name": "S4 Internal Follower", "email": "ops@s4-follower.example"})
        follower_copy = self._packet_mail(load, recipient_ids=[(6, 0, follower.ids)])
        carrier_copy = self._packet_mail(load, recipient_ids=[(6, 0, self.carrier.ids)])
        sink = self._sink()
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=follower_copy.ids)
        self.assertEqual(follower_copy.state, "sent", self._mail_diagnosis(follower_copy))
        load.invalidate_recordset()
        self.assertFalse(load.dispatch_sent, "a follower copy is not the carrier receiving the packet")
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=carrier_copy.ids)
        self.assertEqual(carrier_copy.state, "sent", self._mail_diagnosis(carrier_copy))
        load.invalidate_recordset()
        self.assertTrue(load.dispatch_sent, "the carrier copy's confirmed send starts the clock")

    def test_a_carrier_document_composer_never_tags_the_packet_header(self):
        """Review item 5: only the dispatch packet starts the ACK clock; a BOL or Delivery Order does not."""
        load = self._scheduled_load()
        load.action_dispatch()
        before = self.env["mail.mail"].search([("model", "=", "plasticos.load"), ("res_id", "=", load.id)])
        self._open(load.action_send_delivery_order()).action_send_mail()
        self._open(load.action_send_bol_pickup()).action_send_mail()
        created = self.env["mail.mail"].search([("model", "=", "plasticos.load"), ("res_id", "=", load.id)]) - before
        self.assertTrue(created, "the document composers produced carrier mail")
        for mail in created:
            self.assertNotIn("X-Plasticos-Release", mail.headers or "", self._mail_diagnosis(mail))
        sink = self._sink()
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=created.ids)
        load.invalidate_recordset()
        self.assertFalse(load.dispatch_sent, "a carrier document is not the dispatch packet")

    def test_one_invalid_co_recipient_does_not_stop_the_clock(self):
        """Review O2: the transport's sent state is the gate, not the absence of any failure_type.

        The carrier is reached even though a co-recipient's address is invalid, so the clock
        starts. Mirror (review R1): a reached non-carrier with the same bad co-recipient does not.
        """
        load = self._scheduled_load()
        load.action_dispatch()
        invalid = self.env["res.partner"].create({"name": "S4 Broken Address", "email": "not-an-address"})
        packet = self._packet_mail(load, recipient_ids=[(6, 0, (self.carrier | invalid).ids)])
        sink = self._sink()
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=packet.ids)
        load.invalidate_recordset()
        self.assertEqual(packet.state, "sent", "the valid recipient was reached")
        self.assertTrue(load.dispatch_sent, "a confirmed send starts the clock despite one bad co-recipient")

        other = self._scheduled_load()
        other.action_dispatch()
        bystander = self.env["res.partner"].create({"name": "S4 Valid Dispatcher", "email": "desk@s4-carrier.example"})
        mirror = self._packet_mail(other, recipient_ids=[(6, 0, (bystander | invalid).ids)])
        with sink[0], sink[1], sink[2]:
            self.env["mail.mail"].process_email_queue(email_ids=mirror.ids)
        other.invalidate_recordset()
        self.assertEqual(mirror.state, "sent", self._mail_diagnosis(mirror))
        self.assertFalse(other.dispatch_sent, "reaching someone other than the carrier starts no clock")

    def test_a_second_direct_packet_never_moves_the_clock(self):
        """Review O3: the direct send keeps the first confirmed time, like the composer path."""
        load = self._scheduled_load()
        load.action_dispatch()
        sink = self._sink()
        template = self.env.ref("plasticos_automation.email_template_dispatch_packet")
        self.assertFalse(template.use_default_to, "default recipients would replace the carrier")
        self.assertEqual(template._render_field("email_to", load.ids)[load.id], self.carrier.email)
        with sink[0], sink[1], sink[2]:
            sent = load.action_send_dispatch_direct()
            self.assertTrue(sent, self._mail_diagnosis(self._last_load_mail(load)))
            first = load.dispatch_sent
            self.assertTrue(first)
            with patch.object(fields.Datetime, "now", lambda *args, **kwargs: first + timedelta(hours=3)):
                self.assertTrue(load.action_send_dispatch_direct())
        self.assertEqual(load.dispatch_sent, first, "the acknowledgement clock and its revision key do not move")

    def test_unchanged_context_still_sends_and_ordinary_notes_are_untouched(self):
        load = self._scheduled_load()
        composer = self._open(load.action_send_dispatch_packet())
        messages_before = len(load.message_ids)
        composer.action_send_mail()
        self.assertGreater(len(load.message_ids), messages_before, "the unchanged packet is posted")
        # An internal note on a held load issues no instruction and is not the guard's business.
        note = (
            self.env["mail.compose.message"]
            .with_context(
                default_model="plasticos.load", default_res_ids=load.ids, default_subtype_xmlid="mail.mt_note"
            )
            .create({"body": "internal"})
        )
        with patch.object(PlasticosLoad, "_physical_release_errors", lambda self, kind: ["Booking rolled."]):
            note.action_send_mail()


@tagged("post_install", "-at_install")
class TestCarrierPaperworkWithoutABuyer(TransactionCase):
    """S4 RP-03-E007..E009: carrier paperwork renders a buyerless load from its own company.

    No sale-order or buyer detail is printed when the load has none, and no literal
    stands in for a missing company (BRS-EXP-08-R001, BRS-EXP-10-R003).
    """

    REPORTS = (
        "plasticos_logistics.report_delivery_order",
        "plasticos_logistics.report_bol_pickup",
        "plasticos_logistics.report_bol_delivery",
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.issuer = cls.env["res.company"].create({"name": "S4 Paperwork Co", "street": "8 Yard Rd"})
        cls.supplier = cls.env["res.partner"].create({"name": "S4 Paper Mill", "is_company": True})
        cls.terminal = cls.env["res.partner"].create({"name": "S4 Paper Ramp", "is_company": True})
        cls.buyer = cls.env["res.partner"].create({"name": "S4 Hidden Buyer", "is_company": True, "customer_rank": 1})

    def _render(self, report_ref, load):
        html, _kind = self.env["ir.actions.report"]._render_qweb_html(report_ref, load.ids)
        return html.decode() if isinstance(html, bytes) else str(html)

    def test_buyerless_paperwork_prints_no_order_or_buyer(self):
        load = self.env["plasticos.load"].create(
            {
                "company_id": self.issuer.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.terminal.id,
            }
        )
        self.assertFalse(load.sale_order_id)
        for report_ref in self.REPORTS:
            with self.subTest(report_ref):
                html = self._render(report_ref, load)
                self.assertIn(self.issuer.name, html)
                self.assertNotIn("Order No.", html)
                self.assertNotIn(self.buyer.name, html)

    def test_sale_backed_paperwork_keeps_its_order_number(self):
        order = self.env["sale.order"].create({"partner_id": self.buyer.id})
        load = self.env["plasticos.load"].create(
            {"sale_order_id": order.id, "pickup_partner_id": self.supplier.id, "delivery_partner_id": self.terminal.id}
        )
        html = self._render("plasticos_logistics.report_bol_delivery", load)
        self.assertIn("Order No.", html)
        self.assertIn(order.name, html)
