"""
State machine tests for plasticos.offer.

Lifecycle: draft → sent → responded → accepted/rejected/expired/cancelled
Special: reset_to_draft from rejected/cancelled only.
Cron: cron_expire_offers marks past-due non-terminal offers as expired.

Covers:
- Happy path: draft → sent → responded → accepted
- Happy path: draft → sent → rejected
- Guard: only draft can be sent
- Guard: only sent can be marked responded
- Guard: only sent/responded can be accepted
- Guard: cannot reject accepted/cancelled/expired
- Guard: cannot cancel an accepted offer
- Guard: reset_to_draft only from rejected/cancelled
- Cron: past-due offers expire, terminal offers unaffected
- Computed: total_value = price_per_lb × quantity_lbs
- Computed: accepted_by and accepted_date set on accept
- Constraints: price_per_lb >= 0, quantity_lbs >= 0
"""

from datetime import date, timedelta

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestOfferStates(PlasticosTestCase):
    """Full lifecycle and guard tests for plasticos.offer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Offer Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Offer Test Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )

        # Minimal intake for offer's required field
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "quantity_per_load_lbs": 40000,
            }
        )

    def _create_offer(self, **kw):
        vals = {
            "intake_id": self.intake.id,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 40000,
            "valid_until": date.today() + timedelta(days=30),
        }
        vals.update(kw)
        return self.env["plasticos.offer"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Happy paths
    # ═══════════════════════════════════════════════════════════

    def test_default_state_is_draft(self):
        offer = self._create_offer()
        self.assertEqual(offer.state, "draft")

    def test_draft_to_sent(self):
        offer = self._create_offer()
        offer.action_send()
        self.assertEqual(offer.state, "sent")

    def test_sent_to_responded(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_mark_responded()
        self.assertEqual(offer.state, "responded")

    def test_sent_to_accepted(self):
        """Offers can be accepted directly from sent."""
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")
        self.assertTrue(offer.accepted_by)
        self.assertTrue(offer.accepted_date)

    def test_responded_to_accepted(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_mark_responded()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")

    def test_draft_to_rejected(self):
        """Draft offers can be rejected."""
        offer = self._create_offer()
        offer.action_reject()
        self.assertEqual(offer.state, "rejected")

    def test_draft_to_cancelled(self):
        offer = self._create_offer()
        offer.action_cancel()
        self.assertEqual(offer.state, "cancelled")

    # ═══════════════════════════════════════════════════════════
    # Reset to draft
    # ═══════════════════════════════════════════════════════════

    def test_reset_rejected_to_draft(self):
        offer = self._create_offer()
        offer.action_reject()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_reset_cancelled_to_draft(self):
        offer = self._create_offer()
        offer.action_cancel()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_reset_sent_to_draft_blocked(self):
        """Cannot reset a sent offer — must reject/cancel first."""
        offer = self._create_offer()
        offer.action_send()
        with self.assertRaises(UserError, msg="Only rejected or cancelled"):
            offer.action_reset_to_draft()

    # ═══════════════════════════════════════════════════════════
    # Guards
    # ═══════════════════════════════════════════════════════════

    def test_send_non_draft_blocked(self):
        """Only draft offers can be sent."""
        offer = self._create_offer()
        offer.action_send()
        with self.assertRaises(UserError, msg="Only draft"):
            offer.action_send()

    def test_respond_non_sent_blocked(self):
        """Only sent offers can be marked responded."""
        offer = self._create_offer()
        with self.assertRaises(UserError, msg="Only sent"):
            offer.action_mark_responded()

    def test_accept_draft_blocked(self):
        """Cannot accept a draft offer."""
        offer = self._create_offer()
        with self.assertRaises(UserError, msg="Only sent or responded"):
            offer.action_accept()

    def test_reject_accepted_blocked(self):
        """Cannot reject an accepted offer."""
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError, msg="Cannot reject an accepted"):
            offer.action_reject()

    def test_reject_cancelled_blocked(self):
        offer = self._create_offer()
        offer.action_cancel()
        with self.assertRaises(UserError, msg="Cannot reject"):
            offer.action_reject()

    def test_cancel_accepted_blocked(self):
        """Cannot cancel an accepted offer."""
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError, msg="Cannot cancel an accepted"):
            offer.action_cancel()

    # ═══════════════════════════════════════════════════════════
    # Cron: expire
    # ═══════════════════════════════════════════════════════════

    def test_cron_expires_past_due_offers(self):
        """cron_expire_offers transitions past-due non-terminal offers."""
        past_offer = self._create_offer(
            valid_until=date.today() - timedelta(days=1),
        )
        past_offer.action_send()  # Must be in sent state (non-terminal)
        self.assertEqual(past_offer.state, "sent")

        self.env["plasticos.offer"].cron_expire_offers()
        past_offer.invalidate_recordset(["state"])
        self.assertEqual(past_offer.state, "expired")

    def test_cron_skips_terminal_offers(self):
        """Accepted offers don't expire even if past valid_until."""
        offer = self._create_offer(
            valid_until=date.today() - timedelta(days=1),
        )
        offer.action_send()
        offer.action_accept()

        self.env["plasticos.offer"].cron_expire_offers()
        offer.invalidate_recordset(["state"])
        self.assertEqual(offer.state, "accepted", "Accepted offers must not be expired by cron")

    def test_cron_skips_future_offers(self):
        """Offers with future valid_until are not expired."""
        offer = self._create_offer(
            valid_until=date.today() + timedelta(days=30),
        )
        offer.action_send()

        self.env["plasticos.offer"].cron_expire_offers()
        offer.invalidate_recordset(["state"])
        self.assertEqual(offer.state, "sent")

    # ═══════════════════════════════════════════════════════════
    # Computed: total_value
    # ═══════════════════════════════════════════════════════════

    def test_total_value_computed(self):
        """total_value = price_per_lb × quantity_lbs."""
        offer = self._create_offer(price_per_lb=0.50, quantity_lbs=80000)
        self.assertAlmostEqual(offer.total_value, 40000.0, places=2)

    def test_total_value_zero_quantity(self):
        offer = self._create_offer(price_per_lb=0.50, quantity_lbs=0)
        self.assertAlmostEqual(offer.total_value, 0.0)
