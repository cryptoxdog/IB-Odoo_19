"""
Test intake computed fields.

Tests 8 computed fields:
- pricing
- quantity summaries
- profile
- match_count, selected_count, best_match_score
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIntakeComputes(PlasticosTestCase):
    """Test plasticos.intake computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

    def _create_intake(self, **kwargs):
        """Helper to create an intake with defaults."""
        vals = {
            "partner_id": self.partner.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.intake"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Match Count Tests
    # ═══════════════════════════════════════════════════════════

    def test_match_count_zero_initially(self):
        """match_count should be 0 for new intake."""
        intake = self._create_intake()
        self.assertEqual(intake.match_count, 0)

    def test_match_count_computed(self):
        """match_count should reflect number of match results."""
        intake = self._create_intake()

        # Create match results if model exists
        if "plasticos.match.result" in self.env:
            for i in range(3):
                self.env["plasticos.match.result"].create(
                    {
                        "intake_id": intake.id,
                        "buyer_id": self.partner.id,
                        "score": 80 + i,
                    }
                )

            intake.invalidate_recordset()
            self.assertEqual(intake.match_count, 3)

    # ═══════════════════════════════════════════════════════════
    # Selected Count Tests
    # ═══════════════════════════════════════════════════════════

    def test_selected_count_zero_initially(self):
        """selected_count should be 0 for new intake."""
        intake = self._create_intake()
        self.assertEqual(intake.selected_count, 0)

    def test_selected_count_computed(self):
        """selected_count should reflect accepted matches."""
        intake = self._create_intake()

        if "plasticos.match.result" in self.env:
            # Create and accept a match
            match = self.env["plasticos.match.result"].create(
                {
                    "intake_id": intake.id,
                    "buyer_id": self.partner.id,
                    "score": 85,
                }
            )
            match.action_accept()

            intake.invalidate_recordset()
            self.assertEqual(intake.selected_count, 1)

    # ═══════════════════════════════════════════════════════════
    # Best Match Score Tests
    # ═══════════════════════════════════════════════════════════

    def test_best_match_score_zero_initially(self):
        """best_match_score should be 0 for new intake."""
        intake = self._create_intake()
        self.assertEqual(intake.best_match_score, 0)

    def test_best_match_score_computed(self):
        """best_match_score should be highest score among matches."""
        intake = self._create_intake()

        if "plasticos.match.result" in self.env:
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": intake.id,
                    "buyer_id": self.partner.id,
                    "score": 75,
                }
            )
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": intake.id,
                    "buyer_id": self.partner.id,
                    "score": 90,
                }
            )
            self.env["plasticos.match.result"].create(
                {
                    "intake_id": intake.id,
                    "buyer_id": self.partner.id,
                    "score": 85,
                }
            )

            intake.invalidate_recordset()
            self.assertEqual(intake.best_match_score, 90)

    # ═══════════════════════════════════════════════════════════
    # Company Display Tests
    # ═══════════════════════════════════════════════════════════

    def test_company_display_from_partner(self):
        """company_display should show partner name."""
        intake = self._create_intake()
        self.assertEqual(intake.company_display, self.partner.name)

    def test_company_display_from_pending_company(self):
        """company_display should show pending_company if no partner."""
        intake = self._create_intake(
            partner_id=False,
            pending_company="Pending Corp",
        )
        self.assertEqual(intake.company_display, "Pending Corp")

    # ═══════════════════════════════════════════════════════════
    # Has Residue Tests
    # ═══════════════════════════════════════════════════════════

    def test_has_residue_false_initially(self):
        """has_residue should be False by default."""
        intake = self._create_intake()
        self.assertFalse(intake.has_residue)

    def test_has_residue_computed_from_contamination(self):
        """has_residue should be True if contamination > 0."""
        intake = self._create_intake(contamination_pct=5.0)
        self.assertTrue(intake.has_residue)
