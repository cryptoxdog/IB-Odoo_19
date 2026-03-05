"""
State machine tests for plasticos.load and plasticos.dispatch.

Load pipeline: draft → awaiting_ready → ready_confirmed → rate_confirmed
               → scheduled → dispatched → picked_up → delivered → closed
               (+ exception branch)

Dispatch pipeline: quoted → dispatched → picked_up → delivered → closed
                   (forward-only, validated by ALLOWED_TRANSITIONS map)

Covers:
- Happy path: full load pipeline draft → closed
- Guard: action_dispatch requires scheduled or rate_confirmed
- Guard: action_close requires both BOL docs attached
- Guard: write() blocks non-allowed fields after dispatch
- Timestamps: dispatched_at, delivered_at, entered_state_at set correctly
- Cycle time: computed from dispatched_at → delivered_at
- Rate memory: _store_rate_memory creates plasticos.rate.memory record
- Dispatch: forward-only transitions enforced
- Dispatch: terminal state rejects all transitions
- Dispatch: skip-state blocked (quoted → picked_up)
"""

from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadStates(TransactionCase):
    """Full lifecycle tests for plasticos.load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Load Test Buyer",
                "is_company": True,
            }
        )
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Load Test Carrier",
                "is_company": True,
            }
        )

    def _create_load(self, **kw):
        """Helper: create load with required sale order."""
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        vals = {
            "name": "LOAD-TEST-001",
            "sale_order_id": so.id,
            "carrier_id": self.carrier.id,
        }
        vals.update(kw)
        return self.env["plasticos.load"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Happy path — full pipeline
    # ═══════════════════════════════════════════════════════════

    def test_default_state_is_draft(self):
        load = self._create_load()
        self.assertEqual(load.state, "draft")

    def test_full_pipeline_draft_to_closed(self):
        """Walk through every state in sequence."""
        load = self._create_load()

        # draft → awaiting_ready (via _transition)
        load._transition("awaiting_ready")
        self.assertEqual(load.state, "awaiting_ready")

        # awaiting_ready → ready_confirmed
        load.action_confirm_ready("Test User")
        self.assertEqual(load.state, "ready_confirmed")
        self.assertEqual(load.ready_confirmed_by, "Test User")
        self.assertTrue(load.ready_confirmed_at)

        # ready_confirmed → rate_confirmed
        load.action_confirm_rate(1500.00)
        self.assertEqual(load.state, "rate_confirmed")
        self.assertEqual(load.rate_amount, 1500.00)
        self.assertTrue(load.rate_confirmed_at)

        # rate_confirmed → scheduled
        now = datetime.now()
        pickup = now + timedelta(days=1)
        delivery = now + timedelta(days=3)
        load.action_schedule(pickup, delivery)
        self.assertEqual(load.state, "scheduled")
        self.assertTrue(load.pickup_datetime)
        self.assertTrue(load.delivery_datetime)

        # scheduled → dispatched
        load.action_dispatch()
        self.assertEqual(load.state, "dispatched")
        self.assertTrue(load.dispatched_at)

        # dispatched → picked_up
        load._transition("picked_up")
        self.assertEqual(load.state, "picked_up")

        # picked_up → delivered
        load._transition("delivered")
        self.assertEqual(load.state, "delivered")
        self.assertTrue(load.delivered_at)

        # delivered → closed (requires BOL docs)
        load.write(
            {
                "bol_pickup_attached": True,
                "bol_delivery_attached": True,
            }
        )
        load.action_close()
        self.assertEqual(load.state, "closed")

    # ═══════════════════════════════════════════════════════════
    # Guards
    # ═══════════════════════════════════════════════════════════

    def test_dispatch_requires_scheduled_or_rate_confirmed(self):
        """action_dispatch raises if not in scheduled/rate_confirmed."""
        load = self._create_load()
        with self.assertRaises(UserError, msg="must be scheduled"):
            load.action_dispatch()

    def test_close_requires_bol_docs(self):
        """action_close raises without BOL pickup and delivery."""
        load = self._create_load()
        load._transition("delivered")
        with self.assertRaises(UserError, msg="BOL documents required"):
            load.action_close()

    def test_close_with_only_pickup_bol_raises(self):
        """Partial BOL (pickup only) still fails."""
        load = self._create_load()
        load._transition("delivered")
        load.write({"bol_pickup_attached": True})
        with self.assertRaises(UserError, msg="BOL documents required"):
            load.action_close()

    # ═══════════════════════════════════════════════════════════
    # Write lock after dispatch
    # ═══════════════════════════════════════════════════════════

    def test_write_blocked_after_dispatch(self):
        """Non-allowed fields are locked after dispatch."""
        load = self._create_load()
        load._transition("dispatched")
        with self.assertRaises(UserError, msg="locked after dispatch"):
            load.write({"rate_amount": 9999.99})

    def test_write_allowed_bol_after_dispatch(self):
        """BOL attachment fields are writable after dispatch."""
        load = self._create_load()
        load._transition("dispatched")
        load.write({"bol_pickup_attached": True})
        self.assertTrue(load.bol_pickup_attached)

    # ═══════════════════════════════════════════════════════════
    # Timestamps & computed
    # ═══════════════════════════════════════════════════════════

    def test_dispatched_at_set_on_dispatch(self):
        load = self._create_load()
        load._transition("dispatched")
        self.assertTrue(load.dispatched_at, "dispatched_at should be set")

    def test_delivered_at_set_on_deliver(self):
        load = self._create_load()
        load._transition("delivered")
        self.assertTrue(load.delivered_at, "delivered_at should be set")

    def test_cycle_time_computed(self):
        """cycle_time_hours = (delivered_at - dispatched_at) in hours."""
        load = self._create_load()
        base = datetime(2026, 3, 1, 8, 0, 0)
        load._transition("dispatched")
        # Force timestamps for deterministic test
        load.write(
            {
                "dispatched_at": base,
                "delivered_at": base + timedelta(hours=36),
            }
        )
        load.invalidate_recordset(["cycle_time_hours"])
        self.assertAlmostEqual(load.cycle_time_hours, 36.0, places=1)

    # ═══════════════════════════════════════════════════════════
    # Rate memory
    # ═══════════════════════════════════════════════════════════

    def test_rate_memory_created_on_confirm_rate(self):
        """action_confirm_rate stores rate in plasticos.rate.memory."""
        load = self._create_load()
        load.action_confirm_rate(2200.00)
        memory = self.env["plasticos.rate.memory"].search(
            [
                ("carrier_id", "=", self.carrier.id),
            ],
            limit=1,
        )
        self.assertTrue(memory, "Rate memory record should exist")
        self.assertEqual(memory.rate_amount, 2200.00)


@tagged("post_install", "-at_install")
class TestDispatchStates(TransactionCase):
    """Forward-only dispatch state machine tests."""

    def _create_dispatch(self, **kw):
        vals = {"name": "DSP-TEST-001"}
        vals.update(kw)
        return self.env["plasticos.dispatch"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Happy path — forward only
    # ═══════════════════════════════════════════════════════════

    def test_default_state_is_quoted(self):
        dsp = self._create_dispatch()
        self.assertEqual(dsp.state, "quoted")

    def test_full_dispatch_pipeline(self):
        """quoted → dispatched → picked_up → delivered → closed."""
        dsp = self._create_dispatch()
        for target in ("dispatched", "picked_up", "delivered", "closed"):
            dsp.action_transition(target)
            self.assertEqual(dsp.state, target)

    # ═══════════════════════════════════════════════════════════
    # Invalid transitions
    # ═══════════════════════════════════════════════════════════

    def test_skip_state_blocked(self):
        """Cannot skip states (quoted → picked_up)."""
        dsp = self._create_dispatch()
        with self.assertRaises(UserError, msg="Cannot transition"):
            dsp.action_transition("picked_up")

    def test_backward_transition_blocked(self):
        """Cannot go backwards (dispatched → quoted)."""
        dsp = self._create_dispatch()
        dsp.action_transition("dispatched")
        with self.assertRaises(UserError, msg="Cannot transition"):
            dsp.action_transition("quoted")

    def test_terminal_state_blocks_all(self):
        """Closed is terminal — no transitions allowed."""
        dsp = self._create_dispatch()
        for s in ("dispatched", "picked_up", "delivered", "closed"):
            dsp.action_transition(s)
        with self.assertRaises(UserError, msg="terminal state"):
            dsp.action_transition("quoted")

    def test_same_state_transition_blocked(self):
        """Cannot transition to current state."""
        dsp = self._create_dispatch()
        with self.assertRaises(UserError, msg="Cannot transition"):
            dsp.action_transition("quoted")
