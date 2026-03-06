"""Tests for plasticos.dispatch — state machine transitions.

Target module: plasticos_logistics
Target model:  plasticos.dispatch

Tests forward-only state machine (quoted → dispatched → picked_up →
delivered → closed), backward/skip blocking.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install", "plasticos", "logistics", "dispatch")
class TestDispatch(PlasticosTestCase):
    """Test dispatch state machine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dispatch = cls.env["plasticos.dispatch"]

    def _create_dispatch(self, state="quoted", **kwargs):
        """Helper: create a dispatch with required fields."""
        vals = {
            "name": "Test Dispatch",
        }
        vals.update(kwargs)
        dispatch = self.Dispatch.create(vals)
        if state != "quoted":
            dispatch.write({"state": state})
        return dispatch

    # ── Valid Forward Transitions (subTest) ─────────────────────

    def test_valid_transitions(self):
        """All valid forward transitions accepted."""
        valid = [
            ("quoted", "dispatched"),
            ("dispatched", "picked_up"),
            ("picked_up", "delivered"),
            ("delivered", "closed"),
        ]
        for from_state, to_state in valid:
            with self.subTest(transition=f"{from_state} → {to_state}"):
                dispatch = self._create_dispatch(from_state)
                dispatch.action_transition(to_state)
                self.assertEqual(dispatch.state, to_state)

    # ── Invalid Transitions (subTest) ──────────────────────────

    def test_invalid_transitions(self):
        """Backward, skip, and self transitions are blocked."""
        invalid = [
            ("quoted", "picked_up", "skip"),
            ("quoted", "delivered", "skip"),
            ("quoted", "closed", "skip"),
            ("dispatched", "quoted", "backward"),
            ("picked_up", "quoted", "backward"),
            ("picked_up", "dispatched", "backward"),
            ("delivered", "quoted", "backward"),
            ("delivered", "dispatched", "backward"),
            ("closed", "quoted", "terminal"),
            ("closed", "dispatched", "terminal"),
            ("closed", "delivered", "terminal"),
        ]
        for from_state, to_state, reason in invalid:
            with self.subTest(transition=f"{from_state} → {to_state} ({reason})"):
                dispatch = self._create_dispatch(from_state)
                with self.assertRaises(UserError):
                    dispatch.action_transition(to_state)

    # ── Self Transitions ───────────────────────────────────────

    def test_self_transition_blocked(self):
        """Cannot transition to current state."""
        for state in ("quoted", "dispatched", "picked_up", "delivered"):
            with self.subTest(state=state):
                dispatch = self._create_dispatch(state)
                with self.assertRaises(UserError):
                    dispatch.action_transition(state)

    # ── Terminal State ─────────────────────────────────────────

    def test_closed_is_terminal(self):
        """Closed dispatch blocks all further transitions."""
        dispatch = self._create_dispatch("closed")
        all_states = ["quoted", "dispatched", "picked_up", "delivered"]
        for target in all_states:
            with self.assertRaises(UserError):
                dispatch.action_transition(target)

    # ── Basic CRUD ─────────────────────────────────────────────

    def test_create_dispatch(self):
        """Dispatch can be created with minimal fields."""
        dispatch = self._create_dispatch()
        self.assertTrue(dispatch.id)
        self.assertEqual(dispatch.state, "quoted")

    def test_default_state_is_quoted(self):
        """New dispatch starts in quoted state."""
        dispatch = self._create_dispatch()
        self.assertEqual(dispatch.state, "quoted")
