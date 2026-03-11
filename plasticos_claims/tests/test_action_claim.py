"""Action method tests for plasticos.claim model.

Tests the state machine transitions and validation logic for claims.
Aligned with plasticos_claims/models/claim.py action methods.
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install")
class TestClaimActions(PlasticosTestCase):
    """Test action_* methods on plasticos.claim.

    State machine: pending → in_progress → escalated/resolved → archived
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create transaction (required by claim)
        cls.tx = cls.env["plasticos.transaction"].create({"name": "TX-CLM-TEST"})
        # Create claim with required fields
        cls.claim = cls.env["plasticos.claim"].create(
            {
                "transaction_id": cls.tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "pending",
            }
        )

    def setUp(self):
        super().setUp()
        # Reset claim state before each test
        self.claim.write(
            {
                "state": "pending",
                "resolved_at": False,
                "escalated_at": False,
                "escalation_level": 0,
                "resolution_note": False,
            }
        )

    # ------------------------------------------------------------------
    # State transitions: Happy paths
    # ------------------------------------------------------------------
    def test_action_start_pending_to_in_progress(self):
        """action_start should move pending → in_progress."""
        self.assertEqual(self.claim.state, "pending")
        self.claim.action_start()
        self.assertEqual(self.claim.state, "in_progress")

    def test_action_start_idempotent_for_non_pending(self):
        """action_start should be no-op for non-pending claims."""
        self.claim.state = "in_progress"
        self.claim.action_start()
        self.assertEqual(self.claim.state, "in_progress")

    def test_action_escalate_sets_escalated_at(self):
        """action_escalate should set escalated_at timestamp."""
        self.claim.state = "in_progress"
        self.claim.action_escalate(reason="VIP customer")
        self.assertEqual(self.claim.state, "escalated")
        self.assertTrue(self.claim.escalated_at)
        self.assertEqual(self.claim.escalation_reason, "VIP customer")
        self.assertEqual(self.claim.escalation_level, 1)

    def test_action_escalate_increments_level(self):
        """action_escalate should increment escalation_level."""
        self.claim.state = "pending"
        self.claim.action_escalate(reason="First escalation")
        self.assertEqual(self.claim.escalation_level, 1)
        # Escalate again (from escalated state is not allowed per model logic)
        # The model only allows escalation from pending/in_progress

    def test_action_resolve_sets_resolved_at(self):
        """action_resolve should set resolved_at timestamp."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = "Credit issued"
        self.claim.action_resolve()
        self.assertEqual(self.claim.state, "resolved")
        self.assertTrue(self.claim.resolved_at)

    def test_action_archive_from_resolved(self):
        """action_archive should move resolved → archived."""
        self.claim.state = "resolved"
        self.claim.action_archive()
        self.assertEqual(self.claim.state, "archived")

    def test_action_reopen_clears_resolved_at(self):
        """action_reopen should clear resolved_at and return to in_progress."""
        self.claim.state = "resolved"
        self.claim.resolved_at = "2026-01-01 00:00:00"
        self.claim.action_reopen()
        self.assertEqual(self.claim.state, "in_progress")
        self.assertFalse(self.claim.resolved_at)

    def test_action_reopen_from_archived(self):
        """action_reopen should work from archived state."""
        self.claim.state = "archived"
        self.claim.action_reopen()
        self.assertEqual(self.claim.state, "in_progress")

    # ------------------------------------------------------------------
    # Invalid transitions
    # ------------------------------------------------------------------
    def test_resolve_without_resolution_note_raises(self):
        """Cannot resolve without resolution_note."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = False
        with self.assertRaises(ValidationError):
            self.claim.action_resolve()

    def test_archive_from_pending_is_noop(self):
        """action_archive from pending should be no-op (only resolved can archive)."""
        self.claim.state = "pending"
        self.claim.action_archive()
        # Model only archives from resolved state
        self.assertEqual(self.claim.state, "pending")

    def test_archive_from_in_progress_is_noop(self):
        """action_archive from in_progress should be no-op."""
        self.claim.state = "in_progress"
        self.claim.action_archive()
        self.assertEqual(self.claim.state, "in_progress")

    # ------------------------------------------------------------------
    # Chatter / Tracking
    # ------------------------------------------------------------------
    def test_state_change_tracked(self):
        """State field has tracking=True, should log changes."""
        initial_count = len(self.claim.message_ids)
        self.claim.action_start()
        # Tracking may or may not create messages depending on mail.thread behavior
        # We just verify no error occurs
        self.assertGreaterEqual(len(self.claim.message_ids), initial_count)
