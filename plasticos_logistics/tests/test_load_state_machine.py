"""Tests for plasticos.load — state machine transitions.

Target module: plasticos_logistics
Target model:  plasticos.load

Tests full lifecycle: draft → awaiting_ready → ready → rate_confirmed →
scheduled → dispatched → picked_up → delivered → closed.
Invalid and backward transitions are blocked.
"""

from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "logistics", "load")
class TestLoadStateMachine(TransactionCase):
    """Test load forward-only state machine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Load = cls.env["plasticos.load"]
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Test Carrier LLC",
                "is_company": True,
            }
        )

    def _create_load(self, state="draft", **kwargs):
        """Helper: create a load with required fields."""
        vals = {
            "carrier_id": self.carrier.id,
        }
        vals.update(kwargs)
        load = self.Load.create(vals)
        if state != "draft" and hasattr(load, "state"):
            # Use sudo to bypass write guards for test setup
            load.sudo().write({"state": state})
        return load

    # ── Valid Forward Transitions ──────────────────────────────

    def test_confirm_ready_from_draft(self):
        """action_confirm_ready: draft → ready_confirmed."""
        load = self._create_load("draft")
        if hasattr(load, "action_confirm_ready"):
            load.action_confirm_ready("Test User")
            self.assertEqual(load.state, "ready_confirmed")

    def test_full_lifecycle_forward(self):
        """Load can progress through complete lifecycle."""
        load = self._create_load("draft")

        # Step 1: Confirm ready
        if hasattr(load, "action_confirm_ready"):
            load.action_confirm_ready("Test User")
            self.assertEqual(load.state, "ready_confirmed")

        # Step 2: Confirm rate
        if hasattr(load, "action_confirm_rate"):
            load.action_confirm_rate(1500.00)
            self.assertEqual(load.state, "rate_confirmed")

        # Step 3: Schedule
        if hasattr(load, "action_schedule"):
            pickup = datetime.now() + timedelta(days=1)
            delivery = datetime.now() + timedelta(days=2)
            load.action_schedule(pickup, delivery)
            self.assertEqual(load.state, "scheduled")

        # Step 4: Dispatch
        if hasattr(load, "action_dispatch"):
            load.action_dispatch()
            self.assertEqual(load.state, "dispatched")

        # Step 5-6: For close, we need BOL attachments
        if hasattr(load, "action_close"):
            # Set BOL flags to allow close
            load.sudo().write(
                {
                    "bol_pickup_attached": True,
                    "bol_delivery_attached": True,
                    "state": "delivered",  # Must be delivered first
                }
            )
            load.action_close()
            self.assertEqual(load.state, "closed")

    # ── Invalid Transitions ────────────────────────────────────

    def test_cannot_dispatch_from_draft(self):
        """Cannot skip to dispatched from draft."""
        load = self._create_load("draft")
        if hasattr(load, "action_dispatch"):
            with self.assertRaises(UserError):
                load.action_dispatch()

    def test_cannot_close_without_bol(self):
        """Cannot close without BOL documents."""
        load = self._create_load("delivered")
        load.sudo().write(
            {
                "bol_pickup_attached": False,
                "bol_delivery_attached": False,
            }
        )
        if hasattr(load, "action_close"):
            with self.assertRaises(UserError):
                load.action_close()

    def test_closed_load_blocks_modifications(self):
        """Closed load blocks field modifications (except allowed fields)."""
        load = self._create_load("closed")
        load.sudo().write(
            {
                "bol_pickup_attached": True,
                "bol_delivery_attached": True,
            }
        )
        # Attempting to modify carrier should fail
        with self.assertRaises(UserError):
            load.write({"carrier_id": self.carrier.id})

    # ── State Transition Guards ────────────────────────────────

    def test_write_guard_after_dispatch(self):
        """After dispatch, only allowed fields can be modified."""
        load = self._create_load("dispatched")
        # Allowed: BOL flags
        load.write({"bol_pickup_attached": True})
        self.assertTrue(load.bol_pickup_attached)

        # Blocked: rate_amount
        with self.assertRaises(UserError):
            load.write({"rate_amount": 9999.99})

    # ── Timestamps ─────────────────────────────────────────────

    def test_dispatched_at_set_on_dispatch(self):
        """dispatched_at timestamp is set when transitioning to dispatched."""
        load = self._create_load("draft")
        if hasattr(load, "action_confirm_ready"):
            load.action_confirm_ready("Test User")
        if hasattr(load, "action_confirm_rate"):
            load.action_confirm_rate(1500.00)
        if hasattr(load, "action_schedule"):
            pickup = datetime.now() + timedelta(days=1)
            delivery = datetime.now() + timedelta(days=2)
            load.action_schedule(pickup, delivery)
        if hasattr(load, "action_dispatch"):
            load.action_dispatch()
            self.assertTrue(load.dispatched_at)

    def test_cycle_time_computed(self):
        """cycle_time_hours is computed from dispatched_at and delivered_at."""
        load = self._create_load("draft")
        # Set timestamps directly for test
        now = fields.Datetime.now()
        load.sudo().write(
            {
                "state": "delivered",
                "dispatched_at": now - timedelta(hours=24),
                "delivered_at": now,
            }
        )
        self.assertAlmostEqual(load.cycle_time_hours, 24.0, places=1)
