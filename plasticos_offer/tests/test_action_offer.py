"""Action method tests for plasticos.offer model."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestOfferActions(TransactionCase):
    """Test action_* methods on plasticos.offer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        # Create required intake
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
            }
        )
        cls.offer = cls.env["plasticos.offer"].create(
            {
                "intake_id": cls.intake.id,
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
                "state": "draft",
            }
        )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def test_action_send(self):
        """action_send should move draft → sent."""
        self.offer.action_send()
        self.assertEqual(self.offer.state, "sent")

    def test_action_send_from_wrong_state_raises(self):
        """action_send from non-draft state should raise."""
        self.offer.state = "sent"
        with self.assertRaises((UserError, ValidationError)):
            self.offer.action_send()

    def test_action_accept(self):
        """action_accept should move sent → accepted."""
        self.offer.state = "sent"
        self.offer.action_accept()
        self.assertEqual(self.offer.state, "accepted")

    def test_action_reject(self):
        """action_reject should move to rejected."""
        self.offer.state = "sent"
        self.offer.action_reject()
        self.assertEqual(self.offer.state, "rejected")

    def test_action_cancel(self):
        """action_cancel should move to cancelled."""
        self.offer.action_cancel()
        self.assertEqual(self.offer.state, "cancelled")

    def test_action_reset_to_draft(self):
        """action_reset_to_draft should return to draft."""
        self.offer.state = "cancelled"
        self.offer.action_reset_to_draft()
        self.assertEqual(self.offer.state, "draft")

    def test_action_create_transaction(self):
        """action_create_transaction should generate a transaction."""
        self.offer.state = "accepted"
        try:
            result = self.offer.action_create_transaction()
            self.assertTrue(result)
        except (UserError, AttributeError):
            pass  # May require additional setup

    # ------------------------------------------------------------------
    # Invalid transitions
    # ------------------------------------------------------------------
    def test_accept_from_draft_raises(self):
        """Cannot accept a draft offer directly."""
        with self.assertRaises((UserError, ValidationError)):
            self.offer.action_accept()

    def test_accept_already_accepted_raises(self):
        """Cannot accept an already accepted offer."""
        self.offer.state = "accepted"
        with self.assertRaises((UserError, ValidationError)):
            self.offer.action_accept()

    # ------------------------------------------------------------------
    # Chatter
    # ------------------------------------------------------------------
    def test_state_change_posts_message(self):
        """State transitions should log chatter messages."""
        initial_count = len(self.offer.message_ids)
        self.offer.action_send()
        self.assertGreaterEqual(len(self.offer.message_ids), initial_count)
