"""Unit tests for plasticos.offer lifecycle.

Tests cover:
- State transitions: draft → sent → responded → accepted (and reject/cancel paths)
- Guards: send only from draft, respond only from sent, accept only from sent/responded
- Cannot cancel an accepted offer
- Reset to draft only from rejected or cancelled
- Total value and days_until_expiry computed fields
- Cron auto-expire past valid_until
"""

from datetime import date, timedelta

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestOfferLifecycle(PlasticosTestCase):
    """Test offer state transitions and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "PP",
                "code": "pp_test_offer",
                "full_name": "Polypropylene",
                "category": "commodity",
            }
        )
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
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        cls.offer = cls.env["plasticos.offer"].create(
            {
                "intake_id": cls.intake.id,
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
                "price_per_lb": 0.35,
                "quantity_lbs": 40000,
                "valid_until": date.today() + timedelta(days=14),
            }
        )

    # ── Creation ────────────────────────────────────────────────

    def test_offer_starts_draft(self):
        """New offers default to draft state."""
        self.assertEqual(self.offer.state, "draft")

    def test_display_name_format(self):
        """Display name includes intake, buyer, and state."""
        self.assertIn("draft", self.offer.display_name)

    # ── State Transitions — Happy Path ──────────────────────────

    def test_draft_to_sent(self):
        """draft → sent via action_send."""
        self.offer.action_send()
        self.assertEqual(self.offer.state, "sent")

    def test_sent_to_responded(self):
        """sent → responded via action_mark_responded."""
        self.offer.action_send()
        self.offer.action_mark_responded()
        self.assertEqual(self.offer.state, "responded")

    def test_sent_to_accepted(self):
        """sent → accepted via action_accept."""
        self.offer.action_send()
        self.offer.action_accept()
        self.assertEqual(self.offer.state, "accepted")
        self.assertIsNotNone(self.offer.accepted_by)
        self.assertIsNotNone(self.offer.accepted_date)

    def test_responded_to_accepted(self):
        """responded → accepted via action_accept."""
        self.offer.action_send()
        self.offer.action_mark_responded()
        self.offer.action_accept()
        self.assertEqual(self.offer.state, "accepted")

    def test_reject_from_sent(self):
        """sent → rejected via action_reject."""
        self.offer.action_send()
        self.offer.action_reject()
        self.assertEqual(self.offer.state, "rejected")

    def test_cancel_from_draft(self):
        """draft → cancelled via action_cancel."""
        self.offer.action_cancel()
        self.assertEqual(self.offer.state, "cancelled")

    def test_cancel_from_sent(self):
        """sent → cancelled via action_cancel."""
        self.offer.action_send()
        self.offer.action_cancel()
        self.assertEqual(self.offer.state, "cancelled")

    # ── State Guards — Blocked Transitions ──────────────────────

    def test_send_from_sent_blocked(self):
        """Cannot send an already-sent offer."""
        self.offer.action_send()
        with self.assertRaises(UserError):
            self.offer.action_send()

    def test_respond_from_draft_blocked(self):
        """Cannot mark draft offer as responded."""
        with self.assertRaises(UserError):
            self.offer.action_mark_responded()

    def test_accept_from_draft_blocked(self):
        """Cannot accept a draft offer."""
        with self.assertRaises(UserError):
            self.offer.action_accept()

    def test_reject_accepted_blocked(self):
        """Cannot reject an accepted offer."""
        self.offer.action_send()
        self.offer.action_accept()
        with self.assertRaises(UserError):
            self.offer.action_reject()

    def test_cancel_accepted_blocked(self):
        """Cannot cancel an accepted offer."""
        self.offer.action_send()
        self.offer.action_accept()
        with self.assertRaises(UserError):
            self.offer.action_cancel()

    def test_reset_from_draft_blocked(self):
        """Cannot reset a draft offer."""
        with self.assertRaises(UserError):
            self.offer.action_reset_to_draft()

    def test_reset_from_rejected(self):
        """rejected → draft via action_reset_to_draft."""
        self.offer.action_send()
        self.offer.action_reject()
        self.offer.action_reset_to_draft()
        self.assertEqual(self.offer.state, "draft")

    def test_reset_from_cancelled(self):
        """cancelled → draft via action_reset_to_draft."""
        self.offer.action_cancel()
        self.offer.action_reset_to_draft()
        self.assertEqual(self.offer.state, "draft")

    # ── Computed Fields ─────────────────────────────────────────

    def test_total_value_computed(self):
        """total_value = price_per_lb x quantity_lbs."""
        self.assertAlmostEqual(self.offer.total_value, 14000.0, places=2)

    def test_total_value_zero_when_no_price(self):
        """total_value is 0 when price is 0."""
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0,
                "quantity_lbs": 40000,
            }
        )
        self.assertEqual(offer.total_value, 0.0)

    def test_days_until_expiry_positive(self):
        """days_until_expiry is positive for future valid_until."""
        self.assertGreater(self.offer.days_until_expiry, 0)

    def test_days_until_expiry_negative_past(self):
        """days_until_expiry is negative for past valid_until."""
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0.30,
                "quantity_lbs": 10000,
                "valid_until": date.today() - timedelta(days=5),
            }
        )
        self.assertLess(offer.days_until_expiry, 0)

    def test_days_until_expiry_no_date(self):
        """days_until_expiry is 999 when valid_until not set."""
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
            }
        )
        self.assertEqual(offer.days_until_expiry, 999)

    # ── Cron Auto-Expire ────────────────────────────────────────

    def test_cron_expires_past_offers(self):
        """cron_expire_offers marks past-due non-terminal offers as expired."""
        offer1 = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": date.today() - timedelta(days=1),
                "state": "draft",
            }
        )
        offer2 = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": date.today() - timedelta(days=3),
                "state": "sent",
            }
        )
        self.env["plasticos.offer"].cron_expire_offers()
        offer1.invalidate_recordset()
        offer2.invalidate_recordset()
        self.assertEqual(offer1.state, "expired")
        self.assertEqual(offer2.state, "expired")

    def test_cron_skips_accepted_offers(self):
        """cron_expire_offers does NOT expire accepted offers."""
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": date.today() - timedelta(days=1),
            }
        )
        offer.action_send()
        offer.action_accept()
        self.env["plasticos.offer"].cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "accepted")

    def test_cron_skips_future_offers(self):
        """cron_expire_offers does NOT expire future-dated offers."""
        offer = self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": date.today() + timedelta(days=30),
                "state": "sent",
            }
        )
        self.env["plasticos.offer"].cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "sent")
