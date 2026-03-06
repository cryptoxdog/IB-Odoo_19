"""State machine tests for plasticos.offer.

States: draft → sent → responded → accepted | rejected | expired | cancelled
Reset:  rejected/cancelled → draft

Source: plasticos_offer/models/offer.py
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestOfferStateMachine(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Offer = cls.env["plasticos.offer"]
        cls.supplier = cls.env["res.partner"].create({"name": "Supplier SM"})
        cls.buyer = cls.env["res.partner"].create({"name": "Buyer SM"})
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "quantity_per_load_lbs": 1000.0,
                "loads_per_month": 1,
            }
        )

    def _offer(self, **kw):
        vals = {
            "intake_id": self.intake.id,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "price_per_lb": 0.25,
            "quantity_lbs": 2000.0,
            "valid_until": fields.Date.today() + timedelta(days=30),
        }
        vals.update(kw)
        return self.Offer.create(vals)

    # ── Initial state ────────────────────────────────────────
    def test_create_defaults_to_draft(self):
        offer = self._offer()
        self.assertEqual(offer.state, "draft")

    def test_sequence_auto_assigned(self):
        offer = self._offer()
        self.assertNotEqual(offer.name, "/")

    # ── draft → sent ─────────────────────────────────────────
    def test_send_from_draft(self):
        offer = self._offer()
        offer.action_send()
        self.assertEqual(offer.state, "sent")

    def test_send_from_non_draft_raises(self):
        offer = self._offer()
        offer.action_send()
        with self.assertRaises(UserError):
            offer.action_send()

    # ── sent → responded ─────────────────────────────────────
    def test_mark_responded_from_sent(self):
        offer = self._offer()
        offer.action_send()
        offer.action_mark_responded()
        self.assertEqual(offer.state, "responded")

    def test_mark_responded_from_non_sent_raises(self):
        offer = self._offer()
        with self.assertRaises(UserError):
            offer.action_mark_responded()

    # ── sent/responded → accepted ────────────────────────────
    def test_accept_from_sent(self):
        offer = self._offer()
        offer.action_send()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")
        self.assertTrue(offer.accepted_by)
        self.assertTrue(offer.accepted_date)

    def test_accept_from_responded(self):
        offer = self._offer()
        offer.action_send()
        offer.action_mark_responded()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")

    def test_accept_from_draft_raises(self):
        offer = self._offer()
        with self.assertRaises(UserError):
            offer.action_accept()

    # ── reject ───────────────────────────────────────────────
    def test_reject_from_sent(self):
        offer = self._offer()
        offer.action_send()
        offer.action_reject()
        self.assertEqual(offer.state, "rejected")

    def test_reject_accepted_raises(self):
        offer = self._offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_reject()

    # ── cancel ───────────────────────────────────────────────
    def test_cancel_from_draft(self):
        offer = self._offer()
        offer.action_cancel()
        self.assertEqual(offer.state, "cancelled")

    def test_cancel_accepted_raises(self):
        offer = self._offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_cancel()

    # ── reset to draft ───────────────────────────────────────
    def test_reset_rejected_to_draft(self):
        offer = self._offer()
        offer.action_send()
        offer.action_reject()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_reset_cancelled_to_draft(self):
        offer = self._offer()
        offer.action_cancel()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_reset_accepted_raises(self):
        offer = self._offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_reset_to_draft()

    # ── Expiry cron ──────────────────────────────────────────
    def test_cron_expires_past_valid_until(self):
        offer = self._offer(valid_until=fields.Date.today() - timedelta(days=1))
        offer.action_send()
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "expired")

    def test_cron_does_not_expire_accepted(self):
        offer = self._offer(valid_until=fields.Date.today() - timedelta(days=1))
        offer.action_send()
        offer.action_accept()
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "accepted")

    def test_cron_does_not_expire_future_offers(self):
        offer = self._offer(valid_until=fields.Date.today() + timedelta(days=30))
        offer.action_send()
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "sent")
