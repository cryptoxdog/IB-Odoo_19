"""Unit tests for plasticos.match.result lifecycle.

Tests cover:
- Record creation and display name format
- State transitions: pending → accepted, pending → rejected
- Guard: only pending results can be accepted or rejected
- Reviewed by/date tracking on acceptance
- Score range constraint (0–100)
- Confidence range constraint (0–100)
- Unique constraint per intake + buyer + run
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMatchResult(TransactionCase):
    """Test match result state transitions and constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Master data ─────────────────────────────────────────
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "LDPE",
                "code": "ldpe_test_match",
                "full_name": "Low-Density Polyethylene",
                "category": "commodity",
            }
        )

        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Match Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.env["res.partner"].create(
            {
                "name": "Match Buyer Alpha",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.buyer2 = cls.env["res.partner"].create(
            {
                "name": "Match Buyer Beta",
                "is_company": True,
                "customer_rank": 1,
            }
        )

        cls.intake = cls.env["plasticos.intake"].create(
            {
                "partner_id": cls.supplier.id,
                "polymer_id": cls.polymer.id,
                "quantity_per_load_lbs": 35000,
            }
        )

        cls.match = cls.env["plasticos.match.result"].create(
            {
                "intake_id": cls.intake.id,
                "buyer_partner_id": cls.buyer.id,
                "score": 85.0,
                "confidence": 90.0,
                "run_id": "run-test-001",
            }
        )

    # ══════════════════════════════════════════════════════════════
    # Creation & Display
    # ══════════════════════════════════════════════════════════════

    def test_match_starts_pending(self):
        """New match results default to pending state."""
        self.assertEqual(self.match.state, "pending")

    def test_display_name_format(self):
        """Display name: intake → buyer (score%)."""
        self.assertIn("→", self.match.display_name)
        self.assertIn("85", self.match.display_name)

    def test_denormalized_polymer(self):
        """intake_polymer denormalized from intake."""
        self.assertEqual(self.match.intake_polymer, "LDPE")

    # ══════════════════════════════════════════════════════════════
    # State Transitions
    # ══════════════════════════════════════════════════════════════

    def test_accept_match(self):
        """pending → accepted via action_accept."""
        self.match.action_accept()
        self.assertEqual(self.match.state, "accepted")
        self.assertIsNotNone(self.match.reviewed_by)
        self.assertIsNotNone(self.match.reviewed_date)

    def test_reject_match(self):
        """pending → rejected via action_reject."""
        match2 = self.env["plasticos.match.result"].create(
            {
                "intake_id": self.intake.id,
                "buyer_partner_id": self.buyer2.id,
                "score": 60.0,
                "confidence": 70.0,
                "run_id": "run-test-001",
            }
        )
        match2.action_reject()
        self.assertEqual(match2.state, "rejected")

    def test_accept_already_accepted_raises(self):
        """Cannot accept a non-pending match result."""
        self.match.action_accept()
        with self.assertRaises(UserError):
            self.match.action_accept()

    def test_reject_already_rejected_raises(self):
        """Cannot reject a non-pending match result."""
        match2 = self.env["plasticos.match.result"].create(
            {
                "intake_id": self.intake.id,
                "buyer_partner_id": self.buyer2.id,
                "score": 55.0,
                "confidence": 65.0,
                "run_id": "run-test-002",
            }
        )
        match2.action_reject()
        with self.assertRaises(UserError):
            match2.action_reject()

    def test_accept_records_reviewer(self):
        """Acceptance records the reviewing user."""
        match3 = self.env["plasticos.match.result"].create(
            {
                "intake_id": self.intake.id,
                "buyer_partner_id": self.buyer2.id,
                "score": 72.0,
                "confidence": 80.0,
                "run_id": "run-test-003",
            }
        )
        match3.action_accept()
        self.assertEqual(match3.reviewed_by.id, self.env.uid)

    # ══════════════════════════════════════════════════════════════
    # Score & Confidence Constraints
    # ══════════════════════════════════════════════════════════════

    def test_score_above_100_raises(self):
        """Score > 100 violates SQL constraint."""
        with self.assertRaises(UserError):
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": self.intake.id,
                    "buyer_partner_id": self.buyer.id,
                    "score": 110.0,
                    "run_id": "run-bad-score",
                }
            )

    def test_score_negative_raises(self):
        """Score < 0 violates SQL constraint."""
        with self.assertRaises(UserError):
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": self.intake.id,
                    "buyer_partner_id": self.buyer.id,
                    "score": -5.0,
                    "run_id": "run-neg-score",
                }
            )

    def test_confidence_above_100_raises(self):
        """Confidence > 100 violates SQL constraint."""
        with self.assertRaises(UserError):
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": self.intake.id,
                    "buyer_partner_id": self.buyer.id,
                    "score": 50.0,
                    "confidence": 150.0,
                    "run_id": "run-bad-conf",
                }
            )

    # ══════════════════════════════════════════════════════════════
    # Unique Constraint per Intake + Buyer + Run
    # ══════════════════════════════════════════════════════════════

    def test_duplicate_match_per_run_raises(self):
        """Same intake + buyer + run_id violates unique constraint."""
        with self.assertRaises(UserError):
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": self.intake.id,
                    "buyer_partner_id": self.buyer.id,
                    "score": 90.0,
                    "run_id": "run-test-001",  # Same as cls.match
                }
            )
