"""Tests for plasticos.dispatch state machine transitions.

Target module: plasticos_logistics
Target model:  plasticos.dispatch
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDispatchStateMachine(PlasticosTestCase):
    """Test dispatch forward-only state machine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dispatch = cls.env["plasticos.dispatch"]

    def _create_dispatch(self, state="quoted"):
        return self.Dispatch.create(
            {
                "name": "DSP-TEST-001",
                "state": state,
            }
        )

    # ── Valid forward transitions ────────────────────────────

    def test_quoted_to_dispatched(self):
        """quoted → dispatched is valid."""
        dispatch = self._create_dispatch("quoted")
        dispatch.action_transition("dispatched")
        self.assertEqual(dispatch.state, "dispatched")

    def test_dispatched_to_picked_up(self):
        """dispatched → picked_up is valid."""
        dispatch = self._create_dispatch("quoted")
        dispatch.action_transition("dispatched")
        dispatch.action_transition("picked_up")
        self.assertEqual(dispatch.state, "picked_up")

    def test_picked_up_to_delivered(self):
        """picked_up → delivered is valid."""
        dispatch = self._create_dispatch("quoted")
        dispatch.action_transition("dispatched")
        dispatch.action_transition("picked_up")
        dispatch.action_transition("delivered")
        self.assertEqual(dispatch.state, "delivered")

    def test_delivered_to_closed(self):
        """delivered → closed is valid."""
        dispatch = self._create_dispatch("quoted")
        dispatch.action_transition("dispatched")
        dispatch.action_transition("picked_up")
        dispatch.action_transition("delivered")
        dispatch.action_transition("closed")
        self.assertEqual(dispatch.state, "closed")

    def test_full_lifecycle(self):
        """Full lifecycle: quoted → dispatched → picked_up → delivered → closed."""
        dispatch = self._create_dispatch("quoted")
        for target in ["dispatched", "picked_up", "delivered", "closed"]:
            dispatch.action_transition(target)
        self.assertEqual(dispatch.state, "closed")

    # ── Invalid transitions ──────────────────────────────────

    def test_skip_state_blocked(self):
        """Cannot skip states (quoted → picked_up)."""
        dispatch = self._create_dispatch("quoted")
        with self.assertRaises(UserError):
            dispatch.action_transition("picked_up")

    def test_backward_transition_blocked(self):
        """Cannot go backward (dispatched → quoted)."""
        dispatch = self._create_dispatch("quoted")
        dispatch.action_transition("dispatched")
        with self.assertRaises(UserError):
            dispatch.action_transition("quoted")

    def test_closed_is_terminal(self):
        """Closed state is terminal — no transitions allowed."""
        dispatch = self._create_dispatch("quoted")
        for target in ["dispatched", "picked_up", "delivered", "closed"]:
            dispatch.action_transition(target)
        with self.assertRaises(UserError):
            dispatch.action_transition("quoted")

    def test_closed_to_dispatched_blocked(self):
        """Cannot transition from closed to dispatched."""
        dispatch = self._create_dispatch("quoted")
        for target in ["dispatched", "picked_up", "delivered", "closed"]:
            dispatch.action_transition(target)
        with self.assertRaises(UserError):
            dispatch.action_transition("dispatched")

    def test_self_transition_blocked(self):
        """Cannot transition to the current state."""
        dispatch = self._create_dispatch("quoted")
        with self.assertRaises(UserError):
            dispatch.action_transition("quoted")
