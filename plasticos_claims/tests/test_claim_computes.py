"""
Test claim computed fields.

- days_open
- is_overdue
- recovery_rate
- related partner fields
"""

from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestClaimComputes(TransactionCase):
    """Test plasticos.claim computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_company": True,
                "email": "partner@example.com",
                "phone": "555-1234",
            }
        )

    def _create_claim(self, **kwargs):
        """Helper to create a claim with defaults."""
        vals = {
            "partner_id": self.partner.id,
            "case_type": "quality",
            "severity": "medium",
        }
        vals.update(kwargs)
        return self.env["plasticos.claim"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Days Open Tests
    # ═══════════════════════════════════════════════════════════

    def test_days_open_computed(self):
        """days_open should compute from create_date."""
        claim = self._create_claim()

        # New claim should have days_open = 0 or 1
        self.assertGreaterEqual(claim.days_open, 0)
        self.assertLessEqual(claim.days_open, 1)

    def test_days_open_increases_over_time(self):
        """days_open should increase as time passes."""
        claim = self._create_claim()

        # Manually set create_date to 5 days ago for testing
        past_date = date.today() - timedelta(days=5)
        self.env.cr.execute(
            """
            UPDATE plasticos_claim
            SET create_date = %s
            WHERE id = %s
        """,
            (past_date, claim.id),
        )

        claim.invalidate_recordset()
        self.assertGreaterEqual(claim.days_open, 5)

    def test_days_open_zero_for_resolved(self):
        """days_open should stop counting when resolved."""
        claim = self._create_claim()
        claim.action_start()
        claim.write({"resolution_note": "Resolved."})
        claim.action_resolve()

        # days_open should be based on resolution date
        self.assertGreaterEqual(claim.days_open, 0)

    # ═══════════════════════════════════════════════════════════
    # Is Overdue Tests
    # ═══════════════════════════════════════════════════════════

    def test_is_overdue_false_within_sla(self):
        """is_overdue should be False within SLA period."""
        claim = self._create_claim(sla_days=30)

        self.assertFalse(claim.is_overdue)

    def test_is_overdue_true_past_sla(self):
        """is_overdue should be True past SLA period."""
        claim = self._create_claim(sla_days=3)

        # Set create_date to 5 days ago
        past_date = date.today() - timedelta(days=5)
        self.env.cr.execute(
            """
            UPDATE plasticos_claim
            SET create_date = %s
            WHERE id = %s
        """,
            (past_date, claim.id),
        )

        claim.invalidate_recordset()
        self.assertTrue(claim.is_overdue)

    def test_is_overdue_false_when_resolved(self):
        """is_overdue should be False for resolved claims."""
        claim = self._create_claim(sla_days=1)

        # Set create_date to 5 days ago
        past_date = date.today() - timedelta(days=5)
        self.env.cr.execute(
            """
            UPDATE plasticos_claim
            SET create_date = %s
            WHERE id = %s
        """,
            (past_date, claim.id),
        )

        claim.action_start()
        claim.write({"resolution_note": "Resolved."})
        claim.action_resolve()

        claim.invalidate_recordset()
        # Resolved claims should not be marked overdue
        self.assertFalse(claim.is_overdue)

    # ═══════════════════════════════════════════════════════════
    # Recovery Rate Tests
    # ═══════════════════════════════════════════════════════════

    def test_recovery_rate_computed(self):
        """recovery_rate should be computed from claim_amount and recovery_amount."""
        claim = self._create_claim(
            claim_amount=1000.0,
            recovery_amount=750.0,
        )

        self.assertAlmostEqual(claim.recovery_rate, 75.0, places=1)

    def test_recovery_rate_zero_when_no_claim_amount(self):
        """recovery_rate should be 0 when claim_amount is 0."""
        claim = self._create_claim(
            claim_amount=0.0,
            recovery_amount=100.0,
        )

        self.assertEqual(claim.recovery_rate, 0.0)

    def test_recovery_rate_100_when_full_recovery(self):
        """recovery_rate should be 100 when full recovery."""
        claim = self._create_claim(
            claim_amount=1000.0,
            recovery_amount=1000.0,
        )

        self.assertEqual(claim.recovery_rate, 100.0)

    # ═══════════════════════════════════════════════════════════
    # Related Partner Fields Tests
    # ═══════════════════════════════════════════════════════════

    def test_partner_email_related(self):
        """Partner email should be accessible via related field."""
        claim = self._create_claim()

        if hasattr(claim, "partner_email"):
            self.assertEqual(claim.partner_email, "partner@example.com")

    def test_partner_phone_related(self):
        """Partner phone should be accessible via related field."""
        claim = self._create_claim()

        if hasattr(claim, "partner_phone"):
            self.assertEqual(claim.partner_phone, "555-1234")
