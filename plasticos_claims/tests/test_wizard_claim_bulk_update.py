"""Tests for Claim Bulk Update Wizard."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError


class TestClaimBulkUpdateWizard(PlasticosTestCase):
    """Test plasticos.claim.bulk.update.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_handler = cls.env["res.users"].create(
            {
                "name": "Claim Handler",
                "login": "claim_handler_test",
            }
        )
        # Create transaction for claims to reference
        cls.tx = cls.env["plasticos.transaction"].create({"name": "TX-BULK-UPDATE"})
        cls.claim1 = cls.env["plasticos.claim"].create(
            {
                "transaction_id": cls.tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "pending",
            }
        )
        cls.claim2 = cls.env["plasticos.claim"].create(
            {
                "transaction_id": cls.tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "state": "in_progress",
            }
        )

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------
    def test_default_get_loads_claims(self):
        """Wizard should populate claim_ids from active_ids."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id, self.claim2.id],
            )
            .create(
                {
                    "action_type": "status",
                    "new_state": "in_progress",
                    "reason": "Batch review",
                }
            )
        )
        self.assertEqual(wiz.claim_count, 2)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def test_no_claims_raises(self):
        """Executing with no claims should raise UserError."""
        wiz = self.env["plasticos.claim.bulk.update.wizard"].create(
            {
                "action_type": "status",
                "new_state": "in_progress",
                "reason": "Empty",
            }
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_status_requires_new_state(self):
        """Status action without new_state should raise."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id],
            )
            .create(
                {
                    "action_type": "status",
                    "reason": "No state",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_resolve_requires_resolution_note(self):
        """Resolving without resolution_note should raise."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id],
            )
            .create(
                {
                    "action_type": "status",
                    "new_state": "resolved",
                    "reason": "Resolve without note",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_assign_requires_user(self):
        """Assign action without assignee_id should raise."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id],
            )
            .create(
                {
                    "action_type": "assign",
                    "reason": "No assignee",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    def test_escalate_requires_reason(self):
        """Escalate action without escalation_reason should raise."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id],
            )
            .create(
                {
                    "action_type": "escalate",
                    "reason": "No escalation reason",
                }
            )
        )
        with self.assertRaises(UserError):
            wiz.action_execute()

    # ------------------------------------------------------------------
    # Execution - status changes
    # ------------------------------------------------------------------
    def test_change_status_success(self):
        """Status action should update claim states."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id, self.claim2.id],
            )
            .create(
                {
                    "action_type": "status",
                    "new_state": "escalated",
                    "reason": "Priority escalation",
                }
            )
        )
        result = wiz.action_execute()
        self.assertEqual(self.claim1.state, "escalated")
        self.assertEqual(self.claim2.state, "escalated")
        self.assertEqual(result["tag"], "display_notification")

    def test_resolve_with_note(self):
        """Resolving claims should set resolved_at and resolution_note."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id],
            )
            .create(
                {
                    "action_type": "status",
                    "new_state": "resolved",
                    "resolution_note": "Issue addressed with credit",
                    "reason": "Resolved per agreement",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.claim1.state, "resolved")
        self.assertEqual(self.claim1.resolution_note, "Issue addressed with credit")
        self.assertTrue(self.claim1.resolved_at)

    def test_archived_claims_skipped_for_non_in_progress(self):
        """Archived claims should be skipped unless target is in_progress."""
        self.claim1.state = "archived"
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id, self.claim2.id],
            )
            .create(
                {
                    "action_type": "status",
                    "new_state": "escalated",
                    "reason": "Skip archived",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.claim1.state, "archived")  # unchanged
        self.assertEqual(self.claim2.state, "escalated")

    # ------------------------------------------------------------------
    # Execution - assign
    # ------------------------------------------------------------------
    def test_assign_success(self):
        """Assign action should set assignee_id on all claims."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id, self.claim2.id],
            )
            .create(
                {
                    "action_type": "assign",
                    "assignee_id": self.user_handler.id,
                    "reason": "New handler",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.claim1.assignee_id, self.user_handler)
        self.assertEqual(self.claim2.assignee_id, self.user_handler)

    # ------------------------------------------------------------------
    # Execution - escalate
    # ------------------------------------------------------------------
    def test_escalate_success(self):
        """Escalate action should call action_escalate on eligible claims."""
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id],
            )
            .create(
                {
                    "action_type": "escalate",
                    "escalation_reason": "Customer VIP",
                    "reason": "Priority client",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.claim1.state, "escalated")

    def test_escalate_skips_resolved_archived(self):
        """Escalate should skip resolved/archived claims."""
        self.claim1.write({"state": "resolved", "resolution_note": "Test resolution"})
        wiz = (
            self.env["plasticos.claim.bulk.update.wizard"]
            .with_context(
                active_ids=[self.claim1.id, self.claim2.id],
            )
            .create(
                {
                    "action_type": "escalate",
                    "escalation_reason": "Urgent review",
                    "reason": "Skip resolved",
                }
            )
        )
        wiz.action_execute()
        self.assertEqual(self.claim1.state, "resolved")  # unchanged
        self.assertEqual(self.claim2.state, "escalated")
