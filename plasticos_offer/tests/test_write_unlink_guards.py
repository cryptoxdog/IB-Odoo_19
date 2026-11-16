"""Test 15 — Write/Unlink Guard Tests (Cross-Model).

Risk: HIGH — Data integrity. Guards prevent corruption across models.

Validates guards on:
  - account.move (covered in test_11, cross-referenced here)
  - plasticos.offer: cancel blocked on accepted
  - plasticos.match.result: accept/reject blocked on non-pending
  - plasticos.intake: reset blocked on won
"""

import os
from unittest.mock import patch

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.addons.plasticos_offer.tests.test_manual_send import send_offer_email
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
        # polymer_id / form_id are optional on the intake; a complete intake keeps these guards off the material gate.
        return self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.default_polymer.id,
                "form_id": self.default_form.id,
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
        # The send action is action_send_offers(), guarded by _assert_status("matched")
        # (plasticos_intake/models/intake.py:897-900).
        intake = self._make_intake(status="draft")
        with self.assertRaises(UserError):
            intake.action_send_offers()

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
                "polymer_id": self.default_polymer.id,
                "form_id": self.default_form.id,
                "quantity_per_load_lbs": 40000,
                "status": "matched",
            }
        )
        with self.assertRaisesRegex(UserError, "without a supplier partner"):
            intake.action_make_po()

    def test_action_match_to_buyers_raises_without_engine(self):
        """Matching without a configured Gate raises UserError (no local scoring fallback).

        The local "Buyer Match Engine" stub was retired (ADR-003-single, M3): the base
        action requires GATE_URL (plasticos_intake/models/intake.py:768-773) and the
        plasticos_matching override refuses via _require_gate_for_ui
        (plasticos_matching/models/intake_extension.py:8-13, 19-21).
        """
        intake = self._make_intake()
        with patch.dict(os.environ, {"GATE_URL": ""}), self.assertRaisesRegex(UserError, "Gate"):
            intake.action_match_to_buyers()


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
                "polymer_id": cls.default_polymer.id,
                "form_id": cls.default_form.id,
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
                "price_per_lb": 0.12,
                "quantity_lbs": 40000,
                "state": state,
            }
        )

    def test_cancel_blocked_on_accepted_offer(self):
        self._skip_check()
        offer = self._make_offer()
        send_offer_email(offer)
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_cancel()

    def test_send_blocked_on_non_draft(self):
        self._skip_check()
        offer = self._make_offer()
        send_offer_email(offer)
        with self.assertRaises(UserError):
            offer.action_send()
