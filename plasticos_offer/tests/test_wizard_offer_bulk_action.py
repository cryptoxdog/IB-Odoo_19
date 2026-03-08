"""Tests for Offer Bulk Action Wizard.

Tests the bulk action wizard for offers.
Aligned with plasticos_offer/wizards/offer_bulk_action_wizard.py.

Actions: send, accept, reject, cancel
"""

from datetime import timedelta

from odoo import fields
from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestOfferBulkActionWizard(PlasticosTestCase):
    """Test plasticos.offer.bulk.action.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create({"name": "Offer Supplier", "is_company": True, "supplier_rank": 1})
        cls.buyer = cls.env["res.partner"].create({"name": "Offer Buyer", "is_company": True, "customer_rank": 1})
        cls.intake = cls.env["plasticos.intake"].create({"partner_id": cls.supplier.id, "quantity_lbs": 40000})
        cls.offer_draft = cls.env["plasticos.offer"].create(
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
        cls.offer_sent = cls.env["plasticos.offer"].create(
            {
                "intake_id": cls.intake.id,
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
                "price_per_lb": 0.30,
                "quantity_lbs": 40000,
                "valid_until": fields.Date.today() + timedelta(days=30),
                "state": "sent",
            }
        )
        cls.offer_responded = cls.env["plasticos.offer"].create(
            {
                "intake_id": cls.intake.id,
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
                "price_per_lb": 0.35,
                "quantity_lbs": 40000,
                "valid_until": fields.Date.today() + timedelta(days=30),
                "state": "responded",
            }
        )

    def setUp(self):
        super().setUp()
        # Reset offer states before each test
        self.offer_draft.write({"state": "draft", "rejection_reason": False})
        self.offer_sent.write({"state": "sent", "rejection_reason": False})
        self.offer_responded.write({"state": "responded", "rejection_reason": False})

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def test_default_get_loads_offers(self):
        """Wizard should populate offer_ids from active_ids."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id, self.offer_sent.id],
            )
            .create(
                {
                    "action_type": "send",
                }
            )
        )
        self.assertEqual(wiz.offer_count, 2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_no_offers_raises(self):
        """Executing without offers should raise UserError."""
        wiz = self.env["plasticos.offer.bulk.action.wizard"].create(
            {
                "action_type": "send",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_reject_requires_reason(self):
        """Reject action without rejection_reason should raise."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id],
            )
            .create(
                {
                    "action_type": "reject",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_send_no_draft_offers_raises(self):
        """Send action with no draft offers should raise."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_sent.id],
            )
            .create(
                {
                    "action_type": "send",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_accept_no_sent_offers_raises(self):
        """Accept action with no sent/responded offers should raise."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id],
            )
            .create(
                {
                    "action_type": "accept",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def test_send_draft_offers(self):
        """Send action should transition draft offers to sent."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id],
            )
            .create(
                {
                    "action_type": "send",
                    "notes": "Batch send",
                }
            )
        )
        result = wiz.action_execute()
        self.assertEqual(self.offer_draft.state, "sent")
        self.assertEqual(result["tag"], "display_notification")

    def test_accept_sent_offers(self):
        """Accept action should transition sent offers to accepted."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_sent.id],
            )
            .create(
                {
                    "action_type": "accept",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.offer_sent.state, "accepted")

    def test_reject_with_reason(self):
        """Reject action with reason should transition and log."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id],
            )
            .create(
                {
                    "action_type": "reject",
                    "rejection_reason": "Price too high",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.offer_draft.state, "rejected")
        self.assertEqual(self.offer_draft.rejection_reason, "Price too high")

    def test_cancel_non_accepted_offers(self):
        """Cancel action should cancel non-accepted offers."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id],
            )
            .create(
                {
                    "action_type": "cancel",
                    "notes": "No longer needed",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.offer_draft.state, "cancelled")

    # ------------------------------------------------------------------
    # Edge cases and filtering
    # ------------------------------------------------------------------
    def test_accept_filters_sent_and_responded(self):
        """Accept should only process sent/responded offers."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id, self.offer_sent.id, self.offer_responded.id],
            )
            .create(
                {
                    "action_type": "accept",
                }
            )
        )
        wiz.action_execute()
        # Draft should remain draft (not in valid states)
        self.assertEqual(self.offer_draft.state, "draft")
        # Sent and responded should be accepted
        self.assertEqual(self.offer_sent.state, "accepted")
        self.assertEqual(self.offer_responded.state, "accepted")

    def test_cancel_skips_accepted_offers(self):
        """Cancel should skip accepted offers."""
        self.offer_sent.state = "accepted"
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id, self.offer_sent.id],
            )
            .create(
                {
                    "action_type": "cancel",
                    "notes": "Bulk cancel",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.offer_draft.state, "cancelled")
        self.assertEqual(self.offer_sent.state, "accepted")  # unchanged

    def test_reject_skips_accepted_and_cancelled(self):
        """Reject should skip accepted/cancelled offers."""
        self.offer_sent.state = "accepted"
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id, self.offer_sent.id],
            )
            .create(
                {
                    "action_type": "reject",
                    "rejection_reason": "Bulk reject",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.offer_draft.state, "rejected")
        self.assertEqual(self.offer_sent.state, "accepted")  # unchanged

    def test_notification_returned(self):
        """All actions should return display_notification."""
        wiz = (
            self.env["plasticos.offer.bulk.action.wizard"]
            .with_context(
                active_ids=[self.offer_draft.id],
            )
            .create(
                {
                    "action_type": "send",
                }
            )
        )
        result = wiz.action_execute()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("params", result)
        self.assertEqual(result["params"]["type"], "success")
