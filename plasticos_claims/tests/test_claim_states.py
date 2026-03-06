"""
State machine tests for plasticos.claim.

Lifecycle: pending → in_progress → escalated → resolved → archived
Special: reopen from resolved/archived → in_progress
Constraint: resolution_note required when resolving

Covers:
- Happy path: pending → in_progress → resolved → archived
- Escalation: from pending and in_progress, level increments
- Guard: resolve requires resolution_note
- Guard: archive only from resolved
- Reopen: resolved → in_progress (clears resolved_at)
- Reopen: archived → in_progress
- Timestamps: escalated_at, resolved_at set correctly
- Computed: days_open > 0 while open, 0 when resolved
- Computed: is_overdue when past SLA
- Computed: recovery_rate = recovery / claimed * 100
- Sequence: auto-generates name via ir.sequence
- Constraint: unique name
"""

from datetime import datetime, timedelta

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClaimStates(PlasticosTestCase):
    """Full lifecycle tests for plasticos.claim."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Minimal fixture chain for claim's required transaction_id ──
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Claim Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Claim Test Buyer",
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

    def _create_claim(self, **kw):
        vals = {
            "transaction_id": self.tx.id,
            "case_type": "buyer_claim",
            "severity": "medium",
        }
        vals.update(kw)
        return self.env["plasticos.claim"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Happy path
    # ═══════════════════════════════════════════════════════════

    def test_default_state_is_pending(self):
        claim = self._create_claim()
        self.assertEqual(claim.state, "pending")

    def test_sequence_auto_generates_name(self):
        claim = self._create_claim()
        self.assertNotEqual(claim.name, "New")
        self.assertTrue(claim.name)

    def test_pending_to_in_progress(self):
        claim = self._create_claim()
        claim.action_start()
        self.assertEqual(claim.state, "in_progress")

    def test_full_lifecycle_to_archived(self):
        """pending → in_progress → resolved → archived."""
        claim = self._create_claim()
        claim.action_start()
        self.assertEqual(claim.state, "in_progress")

        claim.resolution_note = "Resolved: credit issued"
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertTrue(claim.resolved_at)

        claim.action_archive()
        self.assertEqual(claim.state, "archived")

    # ═══════════════════════════════════════════════════════════
    # Escalation
    # ═══════════════════════════════════════════════════════════

    def test_escalate_from_pending(self):
        claim = self._create_claim()
        claim.action_escalate(reason="SLA breach")
        self.assertEqual(claim.state, "escalated")
        self.assertEqual(claim.escalation_level, 1)
        self.assertEqual(claim.escalation_reason, "SLA breach")
        self.assertTrue(claim.escalated_at)

    def test_escalate_from_in_progress(self):
        claim = self._create_claim()
        claim.action_start()
        claim.action_escalate()
        self.assertEqual(claim.state, "escalated")
        self.assertEqual(claim.escalation_level, 1)

    def test_escalation_level_increments(self):
        """Each escalation increments the level counter."""
        claim = self._create_claim()
        claim.action_escalate()
        self.assertEqual(claim.escalation_level, 1)

        # Reopen and re-escalate
        claim.resolution_note = "Reopening"
        claim.action_resolve()
        claim.action_reopen()
        claim.action_escalate()
        self.assertEqual(claim.escalation_level, 2)

    def test_escalate_does_not_apply_to_resolved(self):
        """Escalation from resolved has no effect (guard: pending/in_progress only)."""
        claim = self._create_claim()
        claim.action_start()
        claim.resolution_note = "Done"
        claim.action_resolve()
        # action_escalate checks state in (pending, in_progress)
        old_level = claim.escalation_level
        claim.action_escalate()
        self.assertEqual(claim.escalation_level, old_level, "Escalation should not apply to resolved claims")

    # ═══════════════════════════════════════════════════════════
    # Guards: resolution
    # ═══════════════════════════════════════════════════════════

    def test_resolve_without_note_raises(self):
        """Resolution requires a resolution_note."""
        claim = self._create_claim()
        claim.action_start()
        with self.assertRaises(ValidationError, msg="resolution note"):
            claim.action_resolve()

    def test_resolve_with_note_succeeds(self):
        claim = self._create_claim()
        claim.action_start()
        claim.resolution_note = "Credit issued to buyer"
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")

    def test_constraint_resolution_note_on_state(self):
        """Writing state=resolved with blank note triggers constrains."""
        claim = self._create_claim()
        claim.action_start()
        with self.assertRaises(ValidationError):
            claim.write({"state": "resolved", "resolution_note": False})

    # ═══════════════════════════════════════════════════════════
    # Guards: archive
    # ═══════════════════════════════════════════════════════════

    def test_archive_only_from_resolved(self):
        """Archive does nothing unless state is resolved."""
        claim = self._create_claim()
        claim.action_archive()
        self.assertEqual(claim.state, "pending", "Archive from pending should be no-op")

    # ═══════════════════════════════════════════════════════════
    # Reopen
    # ═══════════════════════════════════════════════════════════

    def test_reopen_resolved_to_in_progress(self):
        claim = self._create_claim()
        claim.action_start()
        claim.resolution_note = "Done"
        claim.action_resolve()
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")
        self.assertFalse(claim.resolved_at, "resolved_at should be cleared on reopen")

    def test_reopen_archived_to_in_progress(self):
        claim = self._create_claim()
        claim.action_start()
        claim.resolution_note = "Done"
        claim.action_resolve()
        claim.action_archive()
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")

    def test_reopen_pending_is_noop(self):
        """Reopen from pending has no effect (guard: resolved/archived only)."""
        claim = self._create_claim()
        claim.action_reopen()
        self.assertEqual(claim.state, "pending")

    # ═══════════════════════════════════════════════════════════
    # Computed fields
    # ═══════════════════════════════════════════════════════════

    def test_days_open_positive_while_pending(self):
        """days_open should be >= 0 for open claims."""
        claim = self._create_claim()
        # Force opened_at to yesterday
        claim.write({"opened_at": datetime.now() - timedelta(days=2)})
        claim.invalidate_recordset(["days_open"])
        self.assertGreaterEqual(claim.days_open, 1)

    def test_days_open_zero_when_resolved(self):
        claim = self._create_claim()
        claim.action_start()
        claim.resolution_note = "Resolved"
        claim.action_resolve()
        claim.invalidate_recordset(["days_open"])
        self.assertEqual(claim.days_open, 0)

    def test_is_overdue_after_sla(self):
        """Claim should be overdue when past SLA hours."""
        claim = self._create_claim(sla_hours=1)
        claim.write({"opened_at": datetime.now() - timedelta(hours=2)})
        claim.invalidate_recordset(["is_overdue"])
        self.assertTrue(claim.is_overdue)

    def test_is_overdue_false_within_sla(self):
        claim = self._create_claim(sla_hours=48)
        claim.invalidate_recordset(["is_overdue"])
        self.assertFalse(claim.is_overdue)

    def test_recovery_rate_computed(self):
        """recovery_rate = (recovery / claimed) * 100."""
        claim = self._create_claim(
            claimed_amount=1000.0,
            recovery_amount=750.0,
        )
        self.assertAlmostEqual(claim.recovery_rate, 75.0, places=1)

    def test_recovery_rate_zero_when_no_claim_amount(self):
        claim = self._create_claim(claimed_amount=0, recovery_amount=100)
        self.assertAlmostEqual(claim.recovery_rate, 0.0)

    def test_recovery_rate_capped_at_100(self):
        """Recovery cannot exceed 100%."""
        claim = self._create_claim(
            claimed_amount=100.0,
            recovery_amount=200.0,
        )
        self.assertAlmostEqual(claim.recovery_rate, 100.0, places=1)
