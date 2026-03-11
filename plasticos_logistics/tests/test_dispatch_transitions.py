"""
Test dispatch transition validation.

Tests forward-only validation using ALLOWED_TRANSITIONS map.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDispatchTransitions(PlasticosTestCase):
    """Test plasticos.load dispatch transitions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls.env["res.partner"].create(
            {
                "name": "Test Carrier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.pickup_partner = cls.env["res.partner"].create(
            {
                "name": "Pickup Location",
                "is_company": True,
            }
        )
        cls.delivery_partner = cls.env["res.partner"].create(
            {
                "name": "Delivery Location",
                "is_company": True,
            }
        )

    def _create_load(self, **kwargs):
        """Helper to create a load with defaults."""
        vals = {
            "carrier_id": self.carrier.id,
            "pickup_partner_id": self.pickup_partner.id,
            "delivery_partner_id": self.delivery_partner.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.load"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Forward-Only Transition Tests
    # ═══════════════════════════════════════════════════════════

    def test_cannot_go_backwards_from_dispatched(self):
        """Cannot transition backwards from dispatched to scheduled."""
        load = self._create_load()
        load.action_confirm_ready()
        load.write({"rate": 500.0})
        load.action_confirm_rate()
        load.write({"scheduled_pickup_date": "2026-03-10"})
        load.action_schedule()
        load.action_dispatch()

        with self.assertRaises(UserError):
            load.write({"state": "scheduled"})

    def test_cannot_go_backwards_from_closed(self):
        """Cannot transition backwards from closed."""
        load = self._create_load()
        load.action_confirm_ready()
        load.write({"rate": 500.0})
        load.action_confirm_rate()
        load.write({"scheduled_pickup_date": "2026-03-10"})
        load.action_schedule()
        load.action_dispatch()
        load.action_close()

        with self.assertRaises(UserError):
            load.write({"state": "dispatched"})

    def test_direct_state_write_blocked(self):
        """Direct state write should be blocked (use action methods)."""
        load = self._create_load()

        with self.assertRaises(UserError):
            load.write({"state": "closed"})

    def test_skip_state_raises_error(self):
        """Cannot skip states in the pipeline."""
        load = self._create_load()

        # Cannot go from draft directly to scheduled
        with self.assertRaises(UserError):
            load.action_schedule()

    def test_cancelled_is_terminal(self):
        """Cancelled state is terminal - cannot transition out."""
        load = self._create_load()
        load.write({"state": "cancelled"})

        with self.assertRaises(UserError):
            load.action_confirm_ready()

    # ═══════════════════════════════════════════════════════════
    # Transition Validation Tests
    # ═══════════════════════════════════════════════════════════

    def test_confirm_rate_requires_rate(self):
        """action_confirm_rate requires rate to be set."""
        load = self._create_load()
        load.action_confirm_ready()

        with self.assertRaises(UserError):
            load.action_confirm_rate()  # No rate set

    def test_schedule_requires_date(self):
        """action_schedule requires scheduled_pickup_date."""
        load = self._create_load()
        load.action_confirm_ready()
        load.write({"rate": 500.0})
        load.action_confirm_rate()

        with self.assertRaises(UserError):
            load.action_schedule()  # No date set
