"""
Test match result state transitions.

Tests:
- pending → accepted
- pending → rejected
- no backwards transitions
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMatchResultStates(TransactionCase):
    """Test plasticos.match.result state machine."""

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

        # Create intake if model exists
        if "plasticos.intake" in cls.env:
            cls.intake = cls.env["plasticos.intake"].create(
                {
                    "partner_id": cls.partner.id,
                }
            )
        else:
            cls.intake = None

    def _create_match_result(self, **kwargs):
        """Helper to create a match result."""
        vals = {
            "buyer_id": self.partner.id,
            "score": 85,
            "confidence": 0.9,
        }
        if self.intake:
            vals["intake_id"] = self.intake.id
        vals.update(kwargs)
        return self.env["plasticos.match.result"].create(vals)

    def test_default_state_is_pending(self):
        """New match result should be in pending state."""
        match = self._create_match_result()
        self.assertEqual(match.state, "pending")

    def test_action_accept(self):
        """action_accept should transition pending → accepted."""
        match = self._create_match_result()
        match.action_accept()
        self.assertEqual(match.state, "accepted")

    def test_action_reject(self):
        """action_reject should transition pending → rejected."""
        match = self._create_match_result()
        match.action_reject()
        self.assertEqual(match.state, "rejected")

    def test_cannot_accept_rejected(self):
        """Cannot accept a rejected match."""
        match = self._create_match_result()
        match.action_reject()

        with self.assertRaises(UserError):
            match.action_accept()

    def test_cannot_reject_accepted(self):
        """Cannot reject an accepted match."""
        match = self._create_match_result()
        match.action_accept()

        with self.assertRaises(UserError):
            match.action_reject()

    def test_all_states_exist(self):
        """Verify all states are defined in the selection."""
        match = self._create_match_result()
        state_field = match._fields["state"]
        expected_states = {"pending", "accepted", "rejected"}
        actual_states = {s[0] for s in state_field.selection}
        self.assertEqual(expected_states, actual_states)
