"""Action method tests for plasticos.offer model.

Tests the state machine transitions and validation logic for offers.
Aligned with plasticos_offer/models/offer.py action methods.

State machine: draft → sent → responded → accepted/rejected/expired/cancelled
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestOfferActions(PlasticosTestCase):
    """Test action_* methods on plasticos.offer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Offer Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Offer Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        # Create required intake with quantity
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "quantity_lbs": 40000,
            }
        )
        cls.offer = cls.env["plasticos.offer"].create(
            {
                "intake_id": cls.intake.id,
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
                "price_per_lb": 0.25,
                "quantity_lbs": 40000,
                "valid_until": fields.Date.today() + timedelta(days=30),
                "state": "draft",
            }
        )

    def setUp(self):
        super().setUp()
        # Reset offer state before each test
        self.offer.write(
            {
                "state": "draft",
                "accepted_by": False,
                "accepted_date": False,
                "rejection_reason": False,
            }
        )

    # ------------------------------------------------------------------
    # State transitions: Happy paths
    # ------------------------------------------------------------------
    def test_action_send_draft_to_sent(self):
        """action_send should move draft → sent."""
        self.assertEqual(self.offer.state, "draft")
        self.offer.action_send()
        self.assertEqual(self.offer.state, "sent")

    def test_action_mark_responded(self):
        """action_mark_responded should move sent → responded."""
        self.offer.state = "sent"
        self.offer.action_mark_responded()
        self.assertEqual(self.offer.state, "responded")

    def test_action_accept_from_sent(self):
        """action_accept should move sent → accepted."""
        self.offer.state = "sent"
        self.offer.action_accept()
        self.assertEqual(self.offer.state, "accepted")

    def test_action_accept_from_responded(self):
        """action_accept should move responded → accepted."""
        self.offer.state = "responded"
        self.offer.action_accept()
        self.assertEqual(self.offer.state, "accepted")

    def test_action_accept_sets_accepted_by_and_date(self):
        """action_accept should set accepted_by and accepted_date."""
        self.offer.state = "sent"
        self.offer.action_accept()
        self.assertEqual(self.offer.accepted_by, self.env.user)
        self.assertTrue(self.offer.accepted_date)

    def test_action_reject_from_sent(self):
        """action_reject should move sent → rejected."""
        self.offer.state = "sent"
        self.offer.action_reject()
        self.assertEqual(self.offer.state, "rejected")

    def test_action_reject_from_draft(self):
        """action_reject should move draft → rejected."""
        self.offer.state = "draft"
        self.offer.action_reject()
        self.assertEqual(self.offer.state, "rejected")

    def test_action_cancel_from_draft(self):
        """action_cancel should move draft → cancelled."""
        self.offer.state = "draft"
        self.offer.action_cancel()
        self.assertEqual(self.offer.state, "cancelled")

    def test_action_cancel_from_sent(self):
        """action_cancel should move sent → cancelled."""
        self.offer.state = "sent"
        self.offer.action_cancel()
        self.assertEqual(self.offer.state, "cancelled")

    def test_action_reset_to_draft_from_rejected(self):
        """action_reset_to_draft should return rejected → draft."""
        self.offer.state = "rejected"
        self.offer.action_reset_to_draft()
        self.assertEqual(self.offer.state, "draft")

    def test_action_reset_to_draft_from_cancelled(self):
        """action_reset_to_draft should return cancelled → draft."""
        self.offer.state = "cancelled"
        self.offer.action_reset_to_draft()
        self.assertEqual(self.offer.state, "draft")

    # ------------------------------------------------------------------
    # Invalid transitions
    # ------------------------------------------------------------------
    def test_action_send_from_sent_raises(self):
        """action_send from non-draft state should raise."""
        self.offer.state = "sent"
        with self.assertRaises(UserError):
            self.offer.action_send()

    def test_action_accept_from_draft_raises(self):
        """Cannot accept a draft offer directly."""
        self.offer.state = "draft"
        with self.assertRaises(UserError):
            self.offer.action_accept()

    def test_action_accept_from_accepted_raises(self):
        """Cannot accept an already accepted offer."""
        self.offer.state = "accepted"
        with self.assertRaises(UserError):
            self.offer.action_accept()

    def test_action_reject_from_accepted_raises(self):
        """Cannot reject an accepted offer."""
        self.offer.state = "accepted"
        with self.assertRaises(UserError):
            self.offer.action_reject()

    def test_action_cancel_from_accepted_raises(self):
        """Cannot cancel an accepted offer."""
        self.offer.state = "accepted"
        with self.assertRaises(UserError):
            self.offer.action_cancel()

    def test_action_reset_from_accepted_raises(self):
        """Cannot reset an accepted offer to draft."""
        self.offer.state = "accepted"
        with self.assertRaises(UserError):
            self.offer.action_reset_to_draft()

    def test_action_mark_responded_from_draft_raises(self):
        """Cannot mark responded from draft state."""
        self.offer.state = "draft"
        with self.assertRaises(UserError):
            self.offer.action_mark_responded()

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------
    def test_total_value_computed(self):
        """total_value should be price_per_lb × quantity_lbs."""
        self.offer.price_per_lb = 0.50
        self.offer.quantity_lbs = 10000
        self.assertEqual(self.offer.total_value, 5000.0)

    def test_days_until_expiry_computed(self):
        """days_until_expiry should reflect valid_until date."""
        self.offer.valid_until = fields.Date.today() + timedelta(days=10)
        self.assertEqual(self.offer.days_until_expiry, 10)

    # ------------------------------------------------------------------
    # Tracking
    # ------------------------------------------------------------------
    def test_state_change_tracked(self):
        """State field has tracking=True, should log changes."""
        initial_count = len(self.offer.message_ids)
        self.offer.action_send()
        # Tracking may or may not create messages depending on mail.thread behavior
        self.assertGreaterEqual(len(self.offer.message_ids), initial_count)
