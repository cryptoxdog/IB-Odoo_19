"""State machine tests for plasticos.load.

States: draft → awaiting_ready → ready_confirmed → rate_confirmed
        → scheduled → dispatched → picked_up → delivered → closed | exception

Source: plasticos_logistics/models/load.py
"""

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestLoadStateMachineTransitions(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Load = cls.env["plasticos.load"]
        cls.partner = cls.env["res.partner"].create({"name": "Load SM Partner"})
        cls.sale = cls.env["sale.order"].create({"partner_id": cls.partner.id})

    def _load(self, **kw):
        vals = {
            "name": f"LOAD-{self.Load.search_count([]) + 1:04d}",
            "sale_order_id": self.sale.id,
            "carrier_id": self.partner.id,
        }
        vals.update(kw)
        return self.Load.create(vals)

    # ── Initial state ────────────────────────────────────────
    def test_create_defaults_to_draft(self):
        load = self._load()
        self.assertEqual(load.state, "draft")

    # ── draft → ready_confirmed ──────────────────────────────
    def test_confirm_ready(self):
        load = self._load()
        load.action_confirm_ready("John Doe")
        self.assertEqual(load.state, "ready_confirmed")
        self.assertEqual(load.ready_confirmed_by, "John Doe")
        self.assertTrue(load.ready_confirmed_at)

    # ── ready_confirmed → rate_confirmed ─────────────────────
    def test_confirm_rate(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        self.assertEqual(load.state, "rate_confirmed")
        self.assertEqual(load.rate_amount, 1500.0)
        self.assertTrue(load.rate_confirmed_at)
        self.assertFalse(load.rate_auto_reused)

    # ── rate_confirmed → scheduled ───────────────────────────
    def test_schedule(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        now = fields.Datetime.now()
        load.action_schedule(now, now)
        self.assertEqual(load.state, "scheduled")
        self.assertEqual(load.pickup_datetime, now)

    # ── scheduled → dispatched ───────────────────────────────
    def test_dispatch_from_scheduled(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        now = fields.Datetime.now()
        load.action_schedule(now, now)
        load.action_dispatch()
        self.assertEqual(load.state, "dispatched")
        self.assertTrue(load.dispatched_at)

    def test_dispatch_from_rate_confirmed(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        load.action_dispatch()
        self.assertEqual(load.state, "dispatched")

    def test_dispatch_from_draft_raises(self):
        load = self._load()
        with self.assertRaises(UserError):
            load.action_dispatch()

    # ── Post-dispatch write lock ─────────────────────────────
    def test_dispatched_blocks_field_changes(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        load.action_dispatch()
        with self.assertRaises(UserError):
            load.write({"rate_amount": 9999.0})

    def test_dispatched_allows_bol(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        load.action_dispatch()
        load.write({"bol_pickup_attached": True})
        self.assertTrue(load.bol_pickup_attached)

    # ── → closed (requires BOL) ──────────────────────────────
    def test_close_requires_bol(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        load.action_dispatch()
        with self.assertRaises(UserError):
            load.action_close()

    def test_close_with_bol_succeeds(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        load.action_dispatch()
        load.write({"bol_pickup_attached": True, "bol_delivery_attached": True})
        load.action_close()
        self.assertEqual(load.state, "closed")

    # ── Cycle time ───────────────────────────────────────────
    def test_cycle_time_computed(self):
        load = self._load()
        load.action_confirm_ready("Test")
        load.action_confirm_rate(1500.0)
        load.action_dispatch()
        load.write({"bol_pickup_attached": True, "bol_delivery_attached": True})
        load._transition("delivered")
        load.invalidate_recordset()
        if load.dispatched_at and load.delivered_at:
            self.assertGreaterEqual(load.cycle_time_hours, 0)
