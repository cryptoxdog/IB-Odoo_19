"""
Test offer expiry cron job.

Tests cron marks old sent offers as expired.
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOfferExpiryCron(TransactionCase):
    """Test plasticos.offer expiry cron job."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    def _create_offer(self, **kwargs):
        """Helper to create an offer with defaults."""
        vals = {
            "buyer_id": self.partner.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 40000,
        }
        vals.update(kwargs)
        return self.env["plasticos.offer"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Cron Job Tests
    # ═══════════════════════════════════════════════════════════

    def test_cron_expires_old_sent_offers(self):
        """Cron should mark old sent offers as expired."""
        # Create offer with past expiry date
        past_date = date.today() - timedelta(days=1)
        offer = self._create_offer(expiry_date=past_date)
        offer.action_send()

        self.assertEqual(offer.state, "sent")

        # Run cron job
        self.env["plasticos.offer"].cron_expire_offers()

        # Refresh and check state
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "expired")

    def test_cron_does_not_expire_future_offers(self):
        """Cron should not expire offers with future expiry date."""
        future_date = date.today() + timedelta(days=30)
        offer = self._create_offer(expiry_date=future_date)
        offer.action_send()

        self.assertEqual(offer.state, "sent")

        # Run cron job
        self.env["plasticos.offer"].cron_expire_offers()

        # Should still be sent
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "sent")

    def test_cron_does_not_expire_draft_offers(self):
        """Cron should not expire draft offers (only sent)."""
        past_date = date.today() - timedelta(days=1)
        offer = self._create_offer(expiry_date=past_date)

        self.assertEqual(offer.state, "draft")

        # Run cron job
        self.env["plasticos.offer"].cron_expire_offers()

        # Should still be draft
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "draft")

    def test_cron_does_not_expire_accepted_offers(self):
        """Cron should not expire accepted offers."""
        past_date = date.today() - timedelta(days=1)
        offer = self._create_offer(expiry_date=past_date)
        offer.action_send()
        offer.action_mark_responded()
        offer.action_accept()

        self.assertEqual(offer.state, "accepted")

        # Run cron job
        self.env["plasticos.offer"].cron_expire_offers()

        # Should still be accepted
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "accepted")

    def test_cron_handles_no_expiry_date(self):
        """Cron should handle offers without expiry date."""
        offer = self._create_offer()  # No expiry_date
        offer.action_send()

        # Run cron job - should not raise
        self.env["plasticos.offer"].cron_expire_offers()

        # Should still be sent
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "sent")

    def test_cron_batch_processing(self):
        """Cron should process multiple offers efficiently."""
        past_date = date.today() - timedelta(days=1)

        # Create multiple offers
        offers = self.env["plasticos.offer"]
        for _ in range(5):
            offer = self._create_offer(expiry_date=past_date)
            offer.action_send()
            offers |= offer

        # Run cron job
        self.env["plasticos.offer"].cron_expire_offers()

        # All should be expired
        for offer in offers:
            offer.invalidate_recordset()
            self.assertEqual(offer.state, "expired")
