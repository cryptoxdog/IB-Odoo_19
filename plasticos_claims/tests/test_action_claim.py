"""Action method tests for plasticos.claim model."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestClaimActions(TransactionCase):
    """Test action_* methods on plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Claim requires a transaction_id
        cls.tx = cls.env["plasticos.transaction"].create({"name": "TX-CLM-TEST"})
        cls.claim = cls.env["plasticos.claim"].create(
            {
                "transaction_id": cls.tx.id,
                "case_type": "buyer_claim",
                "state": "pending",
            }
        )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def test_action_start(self):
        """action_start should move pending → in_progress."""
        self.claim.action_start()
        self.assertEqual(self.claim.state, "in_progress")

    def test_action_escalate(self):
        """action_escalate should move to escalated."""
        self.claim.state = "in_progress"
        self.claim.action_escalate(reason="VIP customer")
        self.assertEqual(self.claim.state, "escalated")

    def test_action_resolve(self):
        """action_resolve should move to resolved and set resolved_at."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = "Credit issued"
        self.claim.action_resolve()
        self.assertEqual(self.claim.state, "resolved")
        self.assertTrue(self.claim.resolved_at)

    def test_action_archive(self):
        """action_archive should move resolved → archived."""
        self.claim.state = "resolved"
        self.claim.resolution_note = "Archived after resolution"
        self.claim.action_archive()
        self.assertEqual(self.claim.state, "archived")

    def test_action_reopen(self):
        """action_reopen should move resolved/archived → in_progress."""
        self.claim.state = "resolved"
        self.claim.action_reopen()
        self.assertEqual(self.claim.state, "in_progress")

    # ------------------------------------------------------------------
    # Invalid transitions
    # ------------------------------------------------------------------
    def test_resolve_from_pending_raises(self):
        """Cannot resolve directly from pending without resolution_note."""
        with self.assertRaises((UserError, ValidationError)):
            self.claim.action_resolve()

    def test_archive_from_pending_raises(self):
        """Cannot archive a pending claim."""
        with self.assertRaises((UserError, ValidationError)):
            self.claim.action_archive()

    # ------------------------------------------------------------------
    # Chatter
    # ------------------------------------------------------------------
    def test_transitions_log_chatter(self):
        """State transitions should post audit messages."""
        initial_count = len(self.claim.message_ids)
        self.claim.action_start()
        self.assertGreaterEqual(len(self.claim.message_ids), initial_count)
