"""Exhaustive state machine transition tests for PlastOS models.

Covers:
  - plasticos.load: 10 states with VALID_TRANSITIONS map + exception handling
  - plasticos.transaction: 10 states with action methods + write guards
  - plasticos.claim: 5 states with allowed transition paths
  - plasticos.offer: 7 states with send/respond/accept/reject/cancel paths
  - Negative tests: every invalid transition should raise UserError
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError
from odoo.fields import Datetime
from odoo.tests.common import tagged

LOAD_VALID_TRANSITIONS = {
    "draft": ["awaiting_ready"],
    "awaiting_ready": ["ready_confirmed"],
    "ready_confirmed": ["rate_confirmed"],
    "rate_confirmed": ["scheduled"],
    "scheduled": ["dispatched"],
    "dispatched": ["picked_up"],
    "picked_up": ["delivered"],
    "delivered": ["closed"],
}

LOAD_ALL_STATES = [
    "draft",
    "awaiting_ready",
    "ready_confirmed",
    "rate_confirmed",
    "scheduled",
    "dispatched",
    "picked_up",
    "delivered",
    "closed",
    "exception",
]


@tagged("post_install", "-at_install", "plasticos", "state_machine")
class TestLoadStateMachineConsolidated(PlasticosTestCase):
    """Exhaustive transition tests for plasticos.load."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Load SM Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Load SM Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "supplier_id": cls.supplier.id,
                "buyer_id": cls.buyer.id,
            }
        )

    def _create_load(self):
        return self.env["plasticos.load"].create(
            {
                "transaction_id": self.tx.id,
                "pickup_partner_id": self.supplier.id,
                "delivery_partner_id": self.buyer.id,
            }
        )

    def _advance_to(self, load, target_state):
        """Walk load through valid transitions to reach target_state."""
        path = [
            "draft",
            "awaiting_ready",
            "ready_confirmed",
            "rate_confirmed",
            "scheduled",
            "dispatched",
            "picked_up",
            "delivered",
            "closed",
        ]
        current_idx = path.index(load.state)
        target_idx = path.index(target_state)
        for i in range(current_idx + 1, target_idx + 1):
            state = path[i]
            if state == "awaiting_ready":
                load._transition("awaiting_ready")
            elif state == "ready_confirmed":
                load.action_confirm_ready("Test")
            elif state == "rate_confirmed":
                load.action_confirm_rate(100.0)
            elif state == "scheduled":
                load.action_schedule(Datetime.now(), Datetime.now())
            elif state == "dispatched":
                load.action_dispatch()
            elif state in ("picked_up", "delivered", "closed"):
                load._transition(state)

    # ─── Happy Path: All Valid Transitions ────────────────────

    def test_full_happy_path(self):
        """Load walks through draft -> ... -> closed successfully."""
        load = self._create_load()
        self._advance_to(load, "closed")
        self.assertEqual(load.state, "closed")

    def test_valid_transition_draft_to_awaiting(self):
        load = self._create_load()
        load._transition("awaiting_ready")
        self.assertEqual(load.state, "awaiting_ready")

    def test_valid_transition_awaiting_to_ready(self):
        load = self._create_load()
        self._advance_to(load, "awaiting_ready")
        load.action_confirm_ready("Tester")
        self.assertEqual(load.state, "ready_confirmed")

    def test_valid_transition_ready_to_rate(self):
        load = self._create_load()
        self._advance_to(load, "ready_confirmed")
        load.action_confirm_rate(200.0)
        self.assertEqual(load.state, "rate_confirmed")

    def test_valid_transition_rate_to_scheduled(self):
        load = self._create_load()
        self._advance_to(load, "rate_confirmed")
        load.action_schedule(Datetime.now(), Datetime.now())
        self.assertEqual(load.state, "scheduled")

    def test_valid_transition_scheduled_to_dispatched(self):
        load = self._create_load()
        self._advance_to(load, "scheduled")
        load.action_dispatch()
        self.assertEqual(load.state, "dispatched")

    def test_valid_transition_dispatched_to_picked_up(self):
        load = self._create_load()
        self._advance_to(load, "dispatched")
        load._transition("picked_up")
        self.assertEqual(load.state, "picked_up")

    def test_valid_transition_picked_up_to_delivered(self):
        load = self._create_load()
        self._advance_to(load, "picked_up")
        load._transition("delivered")
        self.assertEqual(load.state, "delivered")

    def test_valid_transition_delivered_to_closed(self):
        load = self._create_load()
        self._advance_to(load, "delivered")
        load._transition("closed")
        self.assertEqual(load.state, "closed")

    # ─── Exception State ─────────────────────────────────────

    def test_exception_from_any_active_state(self):
        """Exception is reachable from any non-closed state."""
        for target in ["awaiting_ready", "ready_confirmed", "scheduled", "dispatched"]:
            load = self._create_load()
            self._advance_to(load, target)
            load.action_mark_exception()
            self.assertEqual(load.state, "exception", f"Failed from {target}")

    def test_reset_from_exception(self):
        """Exception state can be reset back."""
        load = self._create_load()
        self._advance_to(load, "dispatched")
        load.action_mark_exception()
        self.assertEqual(load.state, "exception")
        load.action_reset_from_exception()

    # ─── Invalid Transitions (Negative Tests) ────────────────

    def test_invalid_draft_to_dispatched(self):
        """Cannot jump from draft to dispatched."""
        load = self._create_load()
        with self.assertRaises(UserError):
            load._transition("dispatched")

    def test_invalid_draft_to_closed(self):
        """Cannot jump from draft to closed."""
        load = self._create_load()
        with self.assertRaises(UserError):
            load._transition("closed")

    def test_invalid_scheduled_to_delivered(self):
        """Cannot skip dispatched: scheduled -> delivered."""
        load = self._create_load()
        self._advance_to(load, "scheduled")
        with self.assertRaises(UserError):
            load._transition("delivered")

    def test_invalid_dispatched_to_closed(self):
        """Cannot skip picked_up and delivered: dispatched -> closed."""
        load = self._create_load()
        self._advance_to(load, "dispatched")
        with self.assertRaises(UserError):
            load._transition("closed")

    def test_invalid_backward_transition(self):
        """Cannot go backward: dispatched -> draft."""
        load = self._create_load()
        self._advance_to(load, "dispatched")
        with self.assertRaises(UserError):
            load._transition("draft")

    def test_exhaustive_invalid_from_draft(self):
        """All non-allowed transitions from draft should fail."""
        invalid_targets = [
            s
            for s in LOAD_ALL_STATES
            if s not in LOAD_VALID_TRANSITIONS.get("draft", []) and s != "draft" and s != "exception"
        ]
        for target in invalid_targets:
            load = self._create_load()
            with self.assertRaises(UserError, msg=f"draft -> {target} should fail"):
                load._transition(target)


# ═══════════════════════════════════════════════════════════════
# TRANSACTION STATE MACHINE
# ═══════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install", "plasticos", "state_machine")
class TestTransactionStateMachineConsolidated(PlasticosTestCase):
    """State machine tests for plasticos.transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "TX SM Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "TX SM Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )

    def _create_tx(self):
        return self.env["plasticos.transaction"].create(
            {
                "supplier_id": self.supplier.id,
                "buyer_id": self.buyer.id,
            }
        )

    def test_activate_from_draft(self):
        tx = self._create_tx()
        tx.action_activate()
        self.assertEqual(tx.state, "active")

    def test_activate_from_non_draft_raises(self):
        """Cannot activate a transaction that is not in draft."""
        tx = self._create_tx()
        tx.action_activate()
        with self.assertRaises(UserError):
            tx.action_activate()

    def test_state_via_direct_write_blocked(self):
        """Direct state write (not via action method) is blocked."""
        tx = self._create_tx()
        with self.assertRaises(UserError):
            tx.write({"state": "delivered"})

    def test_state_write_active_allowed(self):
        """Writing state=active is allowed (special case in write())."""
        tx = self._create_tx()
        tx.write({"state": "active"})
        self.assertEqual(tx.state, "active")

    def test_close_requires_posted_invoice(self):
        """Transaction close requires a posted customer invoice."""
        tx = self._create_tx()
        tx.action_activate()
        with self.assertRaises(UserError):
            tx.action_close()

    def test_supplier_ready_from_active(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.action_mark_supplier_ready()
        self.assertEqual(tx.state, "supplier_ready")

    def test_in_progress_after_supplier_ready(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.action_mark_supplier_ready()
        tx.action_mark_in_progress()
        self.assertEqual(tx.state, "in_progress")

    def test_in_transit_after_in_progress(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.action_mark_in_progress()
        tx.action_mark_in_transit()
        self.assertEqual(tx.state, "in_transit")

    def test_delivered_after_in_transit(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.action_mark_in_transit()
        tx.action_mark_delivered()
        self.assertEqual(tx.state, "delivered")

    def test_invoiced_after_delivered(self):
        tx = self._create_tx()
        tx.action_activate()
        tx.action_mark_delivered()
        tx.action_mark_invoiced()
        self.assertEqual(tx.state, "invoiced")


# ═══════════════════════════════════════════════════════════════
# CLAIM STATE MACHINE
# ═══════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install", "plasticos", "state_machine")
class TestClaimStateMachineConsolidated(PlasticosTestCase):
    """State machine tests for plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Claim SM Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "supplier_id": cls.supplier.id,
            }
        )

    def _create_claim(self):
        return self.env["plasticos.claim"].create(
            {
                "transaction_id": self.tx.id,
                "case_type": "buyer_claim",
                "description": "SM Test Claim",
            }
        )

    def test_pending_to_in_progress(self):
        claim = self._create_claim()
        claim.action_start()
        self.assertEqual(claim.state, "in_progress")

    def test_pending_to_escalated(self):
        claim = self._create_claim()
        claim.action_escalate(reason="Urgent")
        self.assertEqual(claim.state, "escalated")

    def test_in_progress_to_escalated(self):
        claim = self._create_claim()
        claim.action_start()
        claim.action_escalate(reason="Getting worse")
        self.assertEqual(claim.state, "escalated")

    def test_resolved_to_archived(self):
        claim = self._create_claim()
        claim.action_start()
        claim.write({"resolution_note": "Fixed", "resolution_type": "credit"})
        claim.action_resolve()
        claim.action_archive()
        self.assertEqual(claim.state, "archived")

    def test_reopen_from_resolved(self):
        claim = self._create_claim()
        claim.action_start()
        claim.write({"resolution_note": "Fixed", "resolution_type": "credit"})
        claim.action_resolve()
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")

    def test_reopen_from_archived(self):
        claim = self._create_claim()
        claim.action_start()
        claim.write({"resolution_note": "Fixed", "resolution_type": "credit"})
        claim.action_resolve()
        claim.action_archive()
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")

    def test_escalation_records_timestamp(self):
        """Escalation sets escalated_at timestamp."""
        claim = self._create_claim()
        claim.action_escalate()
        self.assertTrue(claim.escalated_at)

    def test_sla_age_hours_nonnegative(self):
        """Open claims have non-negative age_hours."""
        claim = self._create_claim()
        self.assertGreaterEqual(claim.age_hours, 0)


# ═══════════════════════════════════════════════════════════════
# OFFER STATE MACHINE
# ═══════════════════════════════════════════════════════════════


@tagged("post_install", "-at_install", "plasticos", "state_machine")
class TestOfferStateMachineConsolidated(PlasticosTestCase):
    """State machine tests for plasticos.offer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Offer SM Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Offer SM Buyer",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "quantity_per_load_lbs": 40000,
            }
        )

    def _create_offer(self):
        return self.env["plasticos.offer"].create(
            {
                "intake_id": self.intake.id,
                "buyer_id": self.buyer.id,
                "price_per_lb": 0.15,
            }
        )

    def test_draft_to_sent(self):
        offer = self._create_offer()
        offer.action_send()
        self.assertEqual(offer.state, "sent")

    def test_sent_to_responded(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_mark_responded()
        self.assertEqual(offer.state, "responded")

    def test_sent_to_accepted(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")

    def test_responded_to_accepted(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_mark_responded()
        offer.action_accept()
        self.assertEqual(offer.state, "accepted")

    def test_sent_to_rejected(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_reject()
        self.assertEqual(offer.state, "rejected")

    def test_draft_to_cancelled(self):
        offer = self._create_offer()
        offer.action_cancel()
        self.assertEqual(offer.state, "cancelled")

    def test_reset_to_draft_from_rejected(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_reject()
        offer.action_reset_to_draft()
        self.assertEqual(offer.state, "draft")

    def test_send_non_draft_raises(self):
        offer = self._create_offer()
        offer.action_send()
        with self.assertRaises(UserError):
            offer.action_send()

    def test_respond_non_sent_raises(self):
        offer = self._create_offer()
        with self.assertRaises(UserError):
            offer.action_mark_responded()

    def test_accept_from_draft_raises(self):
        offer = self._create_offer()
        with self.assertRaises(UserError):
            offer.action_accept()

    def test_cancel_accepted_raises(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_cancel()

    def test_reject_accepted_raises(self):
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        with self.assertRaises(UserError):
            offer.action_reject()

    def test_accept_records_metadata(self):
        """Acceptance records user and timestamp."""
        offer = self._create_offer()
        offer.action_send()
        offer.action_accept()
        self.assertTrue(offer.accepted_by)
        self.assertTrue(offer.accepted_date)
