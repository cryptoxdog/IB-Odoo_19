"""State machine tests for plasticos.claim.

States: pending → in_progress → escalated → resolved → archived
Reopen: resolved/archived → in_progress

Source: plasticos_claims/models/claim.py
"""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestClaimStateMachine(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Claim = cls.env["plasticos.claim"]
        cls.Tx = cls.env["plasticos.transaction"]
        cls.partner = cls.env["res.partner"].create({"name": "Claim SM Partner"})
        cls.tx = cls.Tx.create(
            {
                "partner_id": cls.partner.id,
                "supplier_id": cls.partner.id,
                "buyer_id": cls.partner.id,
            }
        )

    def _claim(self, **kw):
        vals = {
            "transaction_id": self.tx.id,
            "case_type": "buyer_claim",
            "severity": "medium",
            "claimed_amount": 500.0,
        }
        vals.update(kw)
        return self.Claim.create(vals)

    # ── Initial state ────────────────────────────────────────
    def test_create_defaults_pending(self):
        claim = self._claim()
        self.assertEqual(claim.state, "pending")

    def test_sequence_auto_assigned(self):
        claim = self._claim()
        self.assertNotEqual(claim.name, "New")

    # ── pending → in_progress ────────────────────────────────
    def test_start_from_pending(self):
        claim = self._claim()
        claim.action_start()
        self.assertEqual(claim.state, "in_progress")

    def test_start_idempotent_from_non_pending(self):
        claim = self._claim()
        claim.action_start()
        claim.action_start()  # should not raise, just no-op
        self.assertEqual(claim.state, "in_progress")

    # ── pending/in_progress → escalated ──────────────────────
    def test_escalate_from_pending(self):
        claim = self._claim()
        claim.action_escalate(reason="SLA breach")
        self.assertEqual(claim.state, "escalated")
        self.assertTrue(claim.escalated_at)
        self.assertEqual(claim.escalation_level, 1)
        self.assertEqual(claim.escalation_reason, "SLA breach")

    def test_escalate_from_in_progress(self):
        claim = self._claim()
        claim.action_start()
        claim.action_escalate()
        self.assertEqual(claim.state, "escalated")

    def test_escalate_increments_level(self):
        claim = self._claim()
        claim.action_escalate()
        claim.write({"state": "in_progress"})  # simulate reopen-like
        claim.action_escalate()
        self.assertEqual(claim.escalation_level, 2)

    def test_escalate_assigns_user(self):
        claim = self._claim()
        claim.action_escalate(escalate_to=self.env.user)
        self.assertEqual(claim.escalated_to_id, self.env.user)

    # ── → resolved (requires resolution_note) ────────────────
    def test_resolve_without_note_raises(self):
        claim = self._claim()
        claim.action_start()
        with self.assertRaises(ValidationError):
            claim.action_resolve()

    def test_resolve_with_note_succeeds(self):
        claim = self._claim()
        claim.action_start()
        claim.resolution_note = "Credited buyer $200"
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")
        self.assertTrue(claim.resolved_at)

    def test_resolve_from_escalated(self):
        claim = self._claim()
        claim.action_escalate()
        claim.resolution_note = "Resolved after escalation"
        claim.action_resolve()
        self.assertEqual(claim.state, "resolved")

    # ── resolved → archived ──────────────────────────────────
    def test_archive_from_resolved(self):
        claim = self._claim()
        claim.action_start()
        claim.resolution_note = "Done"
        claim.action_resolve()
        claim.action_archive()
        self.assertEqual(claim.state, "archived")

    def test_archive_from_non_resolved_noop(self):
        claim = self._claim()
        claim.action_archive()
        self.assertEqual(claim.state, "pending")

    # ── reopen: resolved/archived → in_progress ──────────────
    def test_reopen_from_resolved(self):
        claim = self._claim()
        claim.action_start()
        claim.resolution_note = "Temp resolve"
        claim.action_resolve()
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")
        self.assertFalse(claim.resolved_at)

    def test_reopen_from_archived(self):
        claim = self._claim()
        claim.action_start()
        claim.resolution_note = "Done"
        claim.action_resolve()
        claim.action_archive()
        claim.action_reopen()
        self.assertEqual(claim.state, "in_progress")

    # ── SLA / overdue ────────────────────────────────────────
    def test_days_open_computed(self):
        claim = self._claim()
        self.assertGreaterEqual(claim.days_open, 0)

    def test_resolved_claim_not_overdue(self):
        claim = self._claim()
        claim.action_start()
        claim.resolution_note = "Fixed"
        claim.action_resolve()
        self.assertFalse(claim.is_overdue)

    # ── Recovery rate ────────────────────────────────────────
    def test_recovery_rate_computed(self):
        claim = self._claim(claimed_amount=1000.0, recovery_amount=400.0)
        self.assertAlmostEqual(claim.recovery_rate, 40.0)

    def test_recovery_rate_zero_if_no_claim(self):
        claim = self._claim(claimed_amount=0.0, recovery_amount=100.0)
        self.assertEqual(claim.recovery_rate, 0.0)
