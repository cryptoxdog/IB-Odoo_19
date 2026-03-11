"""Test 14 — Offer State Machine & Accept Flow.

Source: plasticos_offer/models/offer.py
Risk: CRITICAL — Core revenue path. Offer acceptance is the gateway
to transaction creation.

Validates:
  - Full state machine: draft → sent → responded → accepted
  - action_accept only from sent or responded
  - action_reject blocks on accepted/cancelled/expired
  - action_cancel blocks on accepted
  - action_reset_to_draft only from rejected or cancelled
  - cron_expire_offers idempotency
  - total_value computation
  - days_until_expiry computation
  - sequence generation
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "offer", "critical")
class TestOfferStateMachine(PlasticosTestCase):
    """Full state machine validation for plasticos.offer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Offer = cls.env["plasticos.offer"]
            cls.skip = False
        except KeyError:
            cls.skip = True
            return

        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Offer Supplier",
                "is_company": True,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Offer Buyer",
                "is_company": True,
            }
        )

        Polymer = cls.env.get("plasticos.polymer")
        Form = cls.env.get("plasticos.material.form")
        polymer = Polymer.create({"name": "PP-Offer"}) if Polymer else False
        form = Form.create({"name": "Regrind-Offer"}) if Form else False

        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": polymer.id if polymer else False,
                "form_id": form.id if form else False,
                "quantity_per_load_lbs": 42000,
            }
        )

    def _skip_check(self):
        if self.skip:
            self.skipTest("plasticos_offer not installed")

    def _make_offer(self, **kw):
        vals = {
            "intake_id": self.intake.id,
            "supplier_id": self.supplier.id,
            "buyer_id": self.buyer.id,
            "price_per_lb": 0.12,
            "quantity_lbs": 42000,
            "valid_until": fields.Date.today() + timedelta(days=30),
        }
        vals.update(kw)
        return self.Offer.create(vals)

    # ── Happy path: draft → sent → responded → accepted ─────
    def test_happy_path_full_lifecycle(self):
        self._skip_check()
        offer = self._make_offer()
        self.assertEqual(offer.state, "draft")

        offer.action_send()
        self.assertEqual(offer.state, "sent")

        offer.action_mark_responded()
        self.assertEqual(offer.state, "responded")

        offer.action_accept()
        self.assertEqual(offer.state, "accepted")
        self.assertEqual(offer.accepted_by.id, self.env.uid)
        self.assertTrue(offer.accepted_date)

    def test_accept_from_sent_succeeds(self):
        """Accept directly from sent (no response step)."""
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")

    # ── Guard: accept only from sent or responded ────────────
    def test_accept_from_draft_raises(self):
        self._skip_check()
        offer = self._make_offer()
        with self.assertRaises(UserError):
            offer.action_accept()

    def test_accept_from_rejected_raises(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        offer.action_reject()
        with self.assertRaises(UserError):
            offer.action_accept()

    def test_accept_from_expired_raises(self):
        self._skip_check()
        offer = self._make_offer(state="expired")
        with self.assertRaises(UserError):
            offer.action_accept()

    def test_accept_from_cancelled_raises(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_cancel()
        with self.assertRaises(UserError):
            offer.action_accept()

    # ── Guard: send only from draft ──────────────────────────
    def test_send_from_sent_raises(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        with self.assertRaises(UserError):
            offer.action_send()

    # ── Guard: respond only from sent ────────────────────────
    def test_respond_from_draft_raises(self):
        self._skip_check()
        offer = self._make_offer()
        with self.assertRaises(UserError):
            offer.action_mark_responded()

    # ── Guard: reject blocks on accepted/cancelled/expired ───
    def test_reject_from_accepted_raises(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_reject()

    def test_reject_from_cancelled_raises(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_cancel()
        with self.assertRaises(UserError):
            offer.action_reject()

    def test_reject_from_expired_raises(self):
        self._skip_check()
        offer = self._make_offer(state="expired")
        with self.assertRaises(UserError):
            offer.action_reject()

    # ── Guard: cancel blocks on accepted ─────────────────────
    def test_cancel_from_accepted_raises(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_cancel()

    # ── Guard: reset only from rejected or cancelled ─────────
    def test_reset_from_draft_raises(self):
        self._skip_check()
        offer = self._make_offer()
        with self.assertRaises(UserError):
            offer.action_reset_to_draft()

    def test_reset_from_rejected_succeeds(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        offer.action_reject()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_reset_from_cancelled_succeeds(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_cancel()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")


@tagged("post_install", "-at_install", "offer")
class TestOfferComputed(PlasticosTestCase):
    """Computed field accuracy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Offer = cls.env["plasticos.offer"]
            cls.skip = False
        except KeyError:
            cls.skip = True
            return

        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Comp Supplier",
                "is_company": True,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Comp Buyer",
                "is_company": True,
            }
        )
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "quantity_per_load_lbs": 40000,
            }
        )

    def _skip_check(self):
        if self.skip:
            self.skipTest("plasticos_offer not installed")

    def test_total_value_computation(self):
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0.15,
                "quantity_lbs": 40000,
            }
        )
        self.assertAlmostEqual(offer.total_value, 6000.0, places=2)

    def test_total_value_zero_when_no_price(self):
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0,
                "quantity_lbs": 40000,
            }
        )
        self.assertAlmostEqual(offer.total_value, 0.0)

    def test_days_until_expiry_positive(self):
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": fields.Date.today() + timedelta(days=10),
            }
        )
        self.assertEqual(offer.days_until_expiry, 10)

    def test_days_until_expiry_negative_when_past(self):
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": fields.Date.today() - timedelta(days=5),
            }
        )
        self.assertEqual(offer.days_until_expiry, -5)

    def test_sequence_generation(self):
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
            }
        )
        self.assertNotEqual(offer.name, "/")
        self.assertTrue(offer.name.startswith("OFR"))


@tagged("post_install", "-at_install", "offer", "cron")
class TestOfferCronExpiry(PlasticosTestCase):
    """cron_expire_offers idempotency and correctness."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Offer = cls.env["plasticos.offer"]
            cls.skip = False
        except KeyError:
            cls.skip = True
            return

        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Cron Supplier",
                "is_company": True,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Cron Buyer",
                "is_company": True,
            }
        )
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "quantity_per_load_lbs": 40000,
            }
        )

    def _skip_check(self):
        if self.skip:
            self.skipTest("plasticos_offer not installed")

    def test_cron_expires_past_due_offers(self):
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": fields.Date.today() - timedelta(days=1),
                "state": "sent",
            }
        )
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "expired")

    def test_cron_does_not_expire_accepted(self):
        """Accepted offers must not be expired by cron."""
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": fields.Date.today() - timedelta(days=1),
                "state": "accepted",
            }
        )
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "accepted")

    def test_cron_idempotent_on_rerun(self):
        """Running cron twice produces same result."""
        self._skip_check()
        offer = self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
                "valid_until": fields.Date.today() - timedelta(days=1),
                "state": "draft",
            }
        )
        self.Offer.cron_expire_offers()
        self.Offer.cron_expire_offers()
        offer.invalidate_recordset()
        self.assertEqual(offer.state, "expired")
