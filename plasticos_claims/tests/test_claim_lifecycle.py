"""Unit tests for plasticos.claim lifecycle and SLA.

Tests cover:
- Claim creation with auto-sequence
- Status workflow (pending → in_progress → escalated → resolved → archived)
- Guard: resolution requires resolution_note
- Escalation tracking (level, timestamp, assignee)
- Reopen from resolved/archived
- SLA computed fields (days_open, is_overdue)
- Financial computed fields (recovery_rate)
"""

from datetime import datetime, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestClaimWorkflow(TransactionCase):
    """Test claim state transitions and guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Claim Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "name": "TX-CLAIM-001",
                "supplier_id": cls.supplier.id,
            }
        )
        cls.claim = cls.env["plasticos.claim"].create(
            {
                "transaction_id": cls.tx.id,
                "case_type": "buyer_claim",
                "severity": "medium",
                "claimed_amount": 5000.0,
            }
        )

    # ── Creation ────────────────────────────────────────────────

    def test_claim_auto_sequence(self):
        """Claim name auto-generated from sequence."""
        self.assertNotEqual(self.claim.name, "New")

    def test_claim_starts_pending(self):
        """New claims default to pending state."""
        self.assertEqual(self.claim.state, "pending")

    def test_default_sla_24_hours(self):
        """Default SLA is 24 hours."""
        self.assertEqual(self.claim.sla_hours, 24)

    # ── Status Transitions — Happy Path ─────────────────────────

    def test_pending_to_in_progress(self):
        """pending → in_progress via action_start."""
        self.claim.action_start()
        self.assertEqual(self.claim.state, "in_progress")

    def test_pending_to_escalated(self):
        """pending → escalated via action_escalate."""
        self.claim.action_escalate()
        self.assertEqual(self.claim.state, "escalated")

    def test_in_progress_to_escalated(self):
        """in_progress → escalated via action_escalate."""
        self.claim.state = "in_progress"
        self.claim.action_escalate(reason="SLA breach")
        self.assertEqual(self.claim.state, "escalated")
        self.assertEqual(self.claim.escalation_reason, "SLA breach")

    def test_escalation_increments_level(self):
        """Each escalation increments escalation_level."""
        self.assertEqual(self.claim.escalation_level, 0)
        self.claim.action_escalate()
        self.assertEqual(self.claim.escalation_level, 1)

    def test_escalation_sets_timestamp(self):
        """Escalation records escalated_at."""
        self.claim.action_escalate()
        self.assertIsNotNone(self.claim.escalated_at)

    def test_resolve_with_note(self):
        """Resolve succeeds when resolution_note is provided."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = "Credited buyer $2000"
        self.claim.action_resolve()
        self.assertEqual(self.claim.state, "resolved")
        self.assertIsNotNone(self.claim.resolved_at)

    def test_resolve_without_note_raises(self):
        """Resolve fails without resolution_note."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = False
        with self.assertRaises(ValidationError):
            self.claim.action_resolve()

    def test_resolved_to_archived(self):
        """resolved → archived via action_archive."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = "Done"
        self.claim.action_resolve()
        self.claim.action_archive()
        self.assertEqual(self.claim.state, "archived")

    def test_archive_only_from_resolved(self):
        """action_archive only works from resolved (conditional, not raise)."""
        self.claim.state = "in_progress"
        self.claim.action_archive()
        self.assertEqual(self.claim.state, "in_progress")

    # ── Reopen ──────────────────────────────────────────────────

    def test_reopen_from_resolved(self):
        """Reopen resolved claim goes to in_progress, clears resolved_at."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = "Resolved too early"
        self.claim.action_resolve()
        self.claim.action_reopen()
        self.assertEqual(self.claim.state, "in_progress")
        self.assertFalse(self.claim.resolved_at)

    def test_reopen_from_archived(self):
        """Reopen archived claim goes to in_progress."""
        self.claim.state = "in_progress"
        self.claim.resolution_note = "Archived too early"
        self.claim.action_resolve()
        self.claim.action_archive()
        self.claim.action_reopen()
        self.assertEqual(self.claim.state, "in_progress")

    # ── Financial Computed Fields ───────────────────────────────

    def test_recovery_rate_computed(self):
        """recovery_rate = (recovery / claimed) x 100."""
        self.claim.claimed_amount = 5000
        self.claim.recovery_amount = 2500
        self.claim.invalidate_recordset()
        self.assertAlmostEqual(self.claim.recovery_rate, 50.0, places=1)

    def test_recovery_rate_zero_when_no_claim(self):
        """recovery_rate is 0 when claimed_amount is 0."""
        self.claim.claimed_amount = 0
        self.claim.recovery_amount = 100
        self.claim.invalidate_recordset()
        self.assertEqual(self.claim.recovery_rate, 0.0)

    def test_recovery_rate_capped_at_100(self):
        """recovery_rate cannot exceed 100%."""
        self.claim.claimed_amount = 1000
        self.claim.recovery_amount = 1500
        self.claim.invalidate_recordset()
        self.assertEqual(self.claim.recovery_rate, 100.0)


@tagged("post_install", "-at_install")
class TestClaimSLA(TransactionCase):
    """Test SLA-related computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "SLA Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.tx = cls.env["plasticos.transaction"].create(
            {
                "name": "TX-SLA-001",
                "supplier_id": cls.supplier.id,
            }
        )

    def test_days_open_increments(self):
        """days_open counts days since opened_at for open claims."""
        claim = self.env["plasticos.claim"].create(
            {
                "transaction_id": self.tx.id,
                "case_type": "inspection",
                "severity": "low",
                "opened_at": datetime.now() - timedelta(days=3),
            }
        )
        claim.invalidate_recordset()
        self.assertGreaterEqual(claim.days_open, 3)

    def test_days_open_zero_when_resolved(self):
        """days_open is 0 for resolved claims."""
        claim = self.env["plasticos.claim"].create(
            {
                "transaction_id": self.tx.id,
                "case_type": "inspection",
                "severity": "low",
                "opened_at": datetime.now() - timedelta(days=5),
            }
        )
        claim.resolution_note = "Fixed"
        claim.action_start()
        claim.action_resolve()
        claim.invalidate_recordset()
        self.assertEqual(claim.days_open, 0)

    def test_is_overdue_true_past_sla(self):
        """is_overdue True when opened_at + sla_hours < now."""
        claim = self.env["plasticos.claim"].create(
            {
                "transaction_id": self.tx.id,
                "case_type": "buyer_claim",
                "severity": "high",
                "sla_hours": 2,
                "opened_at": datetime.now() - timedelta(hours=5),
            }
        )
        claim.invalidate_recordset()
        self.assertTrue(claim.is_overdue)

    def test_is_overdue_false_within_sla(self):
        """is_overdue False when within SLA window."""
        claim = self.env["plasticos.claim"].create(
            {
                "transaction_id": self.tx.id,
                "case_type": "buyer_claim",
                "severity": "low",
                "sla_hours": 48,
                "opened_at": datetime.now() - timedelta(hours=1),
            }
        )
        claim.invalidate_recordset()
        self.assertFalse(claim.is_overdue)

    def test_is_overdue_false_when_resolved(self):
        """is_overdue False for resolved claims regardless of time."""
        claim = self.env["plasticos.claim"].create(
            {
                "transaction_id": self.tx.id,
                "case_type": "buyer_claim",
                "severity": "high",
                "sla_hours": 1,
                "opened_at": datetime.now() - timedelta(hours=48),
            }
        )
        claim.resolution_note = "Done"
        claim.action_start()
        claim.action_resolve()
        claim.invalidate_recordset()
        self.assertFalse(claim.is_overdue)
