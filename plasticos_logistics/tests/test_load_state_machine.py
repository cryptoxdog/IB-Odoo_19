"""Unit tests for plasticos.load state machine.

Tests cover:
- State transitions: draft → awaiting_ready → ready_confirmed → rate_confirmed
  → scheduled → dispatched → picked_up → delivered → closed
- action_confirm_ready records user and timestamp
- action_confirm_rate stores rate and timestamp
- action_schedule sets pickup/delivery datetimes
- action_dispatch guard: must be scheduled or rate_confirmed
- action_close guard: BOL documents required
- Write guard: locked fields after dispatch
- Cycle time computation (dispatched_at → delivered_at)
- Rate memory creation
"""

from datetime import datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadStateMachine(TransactionCase):
    """Test load state transitions and guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Test Carrier Inc",
                "is_company": True,
            }
        )

        # Need a sale order for load creation
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Load Test Customer",
                "is_company": True,
            }
        )

        # Minimal sale order
        product = cls.env["product.product"].search([], limit=1)
        if not product:
            product = cls.env["product.product"].create(
                {
                    "name": "Test Product",
                    "type": "consu",
                }
            )

        cls.sale_order = cls.env["sale.order"].create(
            {
                "partner_id": cls.customer.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 1000,
                        },
                    )
                ],
            }
        )

        cls.load = cls.env["plasticos.load"].create(
            {
                "name": "LOAD-TEST-001",
                "sale_order_id": cls.sale_order.id,
                "carrier_id": cls.carrier.id,
            }
        )

    # ══════════════════════════════════════════════════════════════
    # Creation
    # ══════════════════════════════════════════════════════════════

    def test_load_starts_draft(self):
        """New load starts in draft state."""
        self.assertEqual(self.load.state, "draft")

    # ══════════════════════════════════════════════════════════════
    # State Transitions
    # ══════════════════════════════════════════════════════════════

    def test_confirm_ready(self):
        """action_confirm_ready → ready_confirmed with user and timestamp."""
        self.load.action_confirm_ready("John Doe")
        self.assertEqual(self.load.state, "ready_confirmed")
        self.assertEqual(self.load.ready_confirmed_by, "John Doe")
        self.assertIsNotNone(self.load.ready_confirmed_at)

    def test_confirm_rate(self):
        """action_confirm_rate → rate_confirmed with amount and timestamp."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2500.00)
        self.assertEqual(self.load.state, "rate_confirmed")
        self.assertEqual(self.load.rate_amount, 2500.00)
        self.assertIsNotNone(self.load.rate_confirmed_at)
        self.assertFalse(self.load.rate_auto_reused)

    def test_schedule(self):
        """action_schedule → scheduled with pickup/delivery datetimes."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        pickup = datetime.now() + timedelta(days=1)
        delivery = datetime.now() + timedelta(days=3)
        self.load.action_schedule(pickup, delivery)
        self.assertEqual(self.load.state, "scheduled")
        self.assertIsNotNone(self.load.pickup_datetime)
        self.assertIsNotNone(self.load.delivery_datetime)

    def test_dispatch_from_scheduled(self):
        """action_dispatch from scheduled → dispatched."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        pickup = datetime.now() + timedelta(days=1)
        delivery = datetime.now() + timedelta(days=3)
        self.load.action_schedule(pickup, delivery)
        self.load.action_dispatch()
        self.assertEqual(self.load.state, "dispatched")
        self.assertIsNotNone(self.load.dispatched_at)

    def test_dispatch_from_rate_confirmed(self):
        """action_dispatch from rate_confirmed → dispatched (skip schedule)."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        self.assertEqual(self.load.state, "dispatched")

    def test_dispatch_from_draft_blocked(self):
        """action_dispatch from draft raises UserError."""
        with self.assertRaises(UserError):
            self.load.action_dispatch()

    # ══════════════════════════════════════════════════════════════
    # Close Guard: BOL Required
    # ══════════════════════════════════════════════════════════════

    def test_close_without_bol_raises(self):
        """action_close requires both BOL documents."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        # Missing both BOLs
        with self.assertRaises(UserError):
            self.load.action_close()

    def test_close_with_partial_bol_raises(self):
        """action_close requires BOTH pickup and delivery BOL."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        self.load.bol_pickup_attached = True
        # Missing delivery BOL
        with self.assertRaises(UserError):
            self.load.action_close()

    def test_close_with_both_bols(self):
        """action_close succeeds when both BOLs are attached."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        self.load.bol_pickup_attached = True
        self.load.bol_delivery_attached = True
        self.load.action_close()
        self.assertEqual(self.load.state, "closed")

    # ══════════════════════════════════════════════════════════════
    # Write Guard: Locked After Dispatch
    # ══════════════════════════════════════════════════════════════

    def test_write_blocked_after_dispatch(self):
        """Non-allowed fields blocked after dispatch."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        with self.assertRaises(UserError):
            self.load.write({"carrier_id": self.carrier.id})

    def test_bol_write_allowed_after_dispatch(self):
        """BOL attachment fields can be written after dispatch."""
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        # Should NOT raise
        self.load.write({"bol_pickup_attached": True})
        self.assertTrue(self.load.bol_pickup_attached)

    # ══════════════════════════════════════════════════════════════
    # Cycle Time
    # ══════════════════════════════════════════════════════════════

    def test_cycle_time_computed(self):
        """cycle_time_hours = (delivered_at - dispatched_at) in hours."""
        now = datetime.now()
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(2000.00)
        self.load.action_dispatch()
        # Simulate delivery by manually setting delivered_at
        self.load.write(
            {
                "delivered_at": now + timedelta(hours=36),
                "state": "delivered",
                "entered_state_at": now + timedelta(hours=36),
            }
        )
        self.load.invalidate_recordset()
        self.assertGreater(self.load.cycle_time_hours, 0)

    def test_cycle_time_zero_without_delivery(self):
        """cycle_time_hours is 0 when delivered_at is not set."""
        self.assertEqual(self.load.cycle_time_hours, 0)

    # ══════════════════════════════════════════════════════════════
    # Rate Memory
    # ══════════════════════════════════════════════════════════════

    def test_rate_memory_created_on_confirm(self):
        """Rate confirmation creates a rate memory record."""
        count_before = self.env["plasticos.rate.memory"].search_count([])
        self.load.action_confirm_ready("Jane")
        self.load.action_confirm_rate(3000.00)
        count_after = self.env["plasticos.rate.memory"].search_count([])
        self.assertGreater(count_after, count_before)
