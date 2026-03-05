"""Tests for Offer Bulk Action Wizard."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestOfferBulkActionWizard(TransactionCase):
    """Test plasticos.offer.bulk.action.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Offer Partner",
                "is_company": True,
            }
        )
        cls.offer_draft = cls.env["plasticos.offer"].create(
            {
                "name": "OFF-BA-001",
                "state": "draft",
                "partner_id": cls.partner.id,
            }
        )
        cls.offer_sent = cls.env["plasticos.offer"].create(
            {
                "name": "OFF-BA-002",
                "state": "sent",
                "partner_id": cls.partner.id,
            }
        )

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
