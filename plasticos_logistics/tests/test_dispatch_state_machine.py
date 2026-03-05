"""Unit tests for plasticos.dispatch state machine.

Tests cover:
- Default state is quoted
- Forward transitions: quoted → dispatched → picked_up → delivered → closed
- Backward transition blocked (delivered → dispatched)
- Skip transition blocked (quoted → delivered)
- Terminal state (closed) blocks all transitions
- Invalid state raises UserError
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDispatchStateMachine(TransactionCase):
    """Test dispatch state transitions via ALLOWED_TRANSITIONS."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dispatch = cls.env["plasticos.dispatch"].create(
            {
                "name": "DSP-TEST-001",
            }
        )

    def test_default_state_quoted(self):
        """New dispatch starts in quoted state."""
        self.assertEqual(self.dispatch.state, "quoted")

    def test_quoted_to_dispatched(self):
        """quoted → dispatched via action_transition."""
        self.dispatch.action_transition("dispatched")
        self.assertEqual(self.dispatch.state, "dispatched")

    def test_dispatched_to_picked_up(self):
        """dispatched → picked_up."""
        self.dispatch.action_transition("dispatched")
        self.dispatch.action_transition("picked_up")
        self.assertEqual(self.dispatch.state, "picked_up")

    def test_picked_up_to_delivered(self):
        """picked_up → delivered."""
        self.dispatch.action_transition("dispatched")
        self.dispatch.action_transition("picked_up")
        self.dispatch.action_transition("delivered")
        self.assertEqual(self.dispatch.state, "delivered")

    def test_delivered_to_closed(self):
        """delivered → closed."""
        self.dispatch.action_transition("dispatched")
        self.dispatch.action_transition("picked_up")
        self.dispatch.action_transition("delivered")
        self.dispatch.action_transition("closed")
        self.assertEqual(self.dispatch.state, "closed")

    def test_backward_transition_blocked(self):
        """Cannot go backward: delivered → dispatched."""
        self.dispatch.action_transition("dispatched")
        self.dispatch.action_transition("picked_up")
        self.dispatch.action_transition("delivered")
        with self.assertRaises(UserError):
            self.dispatch.action_transition("dispatched")

    def test_skip_transition_blocked(self):
        """Cannot skip: quoted → delivered."""
        with self.assertRaises(UserError):
            self.dispatch.action_transition("delivered")

    def test_terminal_state_closed(self):
        """Closed state blocks all transitions."""
        self.dispatch.action_transition("dispatched")
        self.dispatch.action_transition("picked_up")
        self.dispatch.action_transition("delivered")
        self.dispatch.action_transition("closed")
        with self.assertRaises(UserError):
            self.dispatch.action_transition("dispatched")

    def test_invalid_state_raises(self):
        """Transition to unknown state raises UserError."""
        with self.assertRaises(UserError):
            self.dispatch.action_transition("nonexistent")
