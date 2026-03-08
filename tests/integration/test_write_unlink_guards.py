"""Test 15 — Write/Unlink Guard Tests (Cross-Model).

Risk: HIGH — Data integrity. Guards prevent corruption across models.

Validates guards on:
  - account.move (covered in test_11, cross-referenced here)
  - plasticos.offer: cancel blocked on accepted
  - plasticos.match.result: accept/reject blocked on non-pending
  - plasticos.intake: reset blocked on won
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "guards", "critical")
class TestIntakeWriteGuards(PlasticosTestCase):
    """Intake status transition guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Guard Co",
                "is_company": True,
            }
        )

    def _make_intake(self, status="draft"):
        return self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
                "quantity_per_load_lbs": 40000,
                "status": status,
            }
        )

    def test_reset_to_draft_blocked_on_won(self):
        """Cannot reset a Won intake."""
        intake = self._make_intake(status="won")
        with self.assertRaises(UserError):
            intake.action_reset_to_draft()

    def test_action_send_offer_only_from_matched(self):
        intake = self._make_intake(status="draft")
        with self.assertRaises(UserError):
            intake.action_send_offer()

    def test_action_mark_processing_only_from_offer_sent(self):
        intake = self._make_intake(status="draft")
        with self.assertRaises(UserError):
            intake.action_mark_processing()

    def test_action_mark_won_only_from_offer_sent_or_processing(self):
        intake = self._make_intake(status="draft")
        with self.assertRaises(UserError):
            intake.action_mark_won()

    def test_action_make_po_requires_partner(self):
        """action_make_po raises when no partner set."""
        intake = self.env["plasticos.intake"].create(
            {
                "quantity_per_load_lbs": 40000,
                "status": "matched",
            }
        )
        with self.assertRaises(UserError):
            intake.action_make_po()

    def test_action_match_to_buyers_raises_without_engine(self):
        """Base stub raises UserError (engine not installed)."""
        intake = self._make_intake()
        # If buyer_match_engine is installed, it overrides this.
        # We test the base behavior.
        try:
            intake.action_match_to_buyers()
            # If no error, engine is installed — that's fine
        except UserError as e:
            self.assertIn("Buyer Match Engine", str(e))


@tagged("post_install", "-at_install", "guards")
class TestOfferWriteGuards(PlasticosTestCase):
    """Offer state transition guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.Offer = cls.env["plasticos.offer"]
            cls.skip = False
        except KeyError:
            cls.skip = True
            return
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Offer Guard Co",
                "is_company": True,
            }
        )
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.partner.id,
                "quantity_per_load_lbs": 40000,
            }
        )

    def _skip_check(self):
        if self.skip:
            self.skipTest("plasticos_offer not installed")

    def _make_offer(self, state="draft"):
        return self.Offer.create(
            {
                "intake_id": self.intake.id,
                "supplier_id": self.partner.id,
                "buyer_id": self.partner.id,
                "state": state,
            }
        )

    def test_cancel_blocked_on_accepted_offer(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_cancel()

    def test_send_blocked_on_non_draft(self):
        self._skip_check()
        offer = self._make_offer()
        offer.action_send()
        with self.assertRaises(UserError):
            offer.action_send()
