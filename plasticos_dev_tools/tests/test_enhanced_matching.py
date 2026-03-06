"""
Test suite for enhanced buyer matching pipeline.

Tests the plasticos.match.result and plasticos.match.exclusion models
which form the core of the buyer matching system.

Migrated from legacy plastic_ai.* namespace to plasticos.* namespace.
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestEnhancedBuyerMatching(PlasticosTestCase):
    """Test enhanced buyer matching with exclusions and result lifecycle."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Intake = cls.env["plasticos.intake"]
        cls.MatchResult = cls.env["plasticos.match.result"]
        cls.MatchExclusion = cls.env["plasticos.match.exclusion"]

        cls.supplier = cls.Partner.create(
            {
                "name": "Test Supplier Co",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        cls.buyer = cls.Partner.create(
            {
                "name": "Test Buyer Inc",
                "is_company": True,
                "customer_rank": 1,
            }
        )
        cls.buyer_facility = cls.Partner.create(
            {
                "name": "Buyer Facility A",
                "is_company": False,
                "parent_id": cls.buyer.id,
            }
        )

        if "plasticos.polymer" in cls.env:
            cls.polymer = cls.env["plasticos.polymer"].create(
                {
                    "name": "HDPE",
                    "code": "HDPE-TEST",
                }
            )
        else:
            cls.polymer = None

        if "plasticos.material.form" in cls.env:
            cls.form = cls.env["plasticos.material.form"].create(
                {
                    "name": "Pellet",
                    "code": "PEL-TEST",
                }
            )
        else:
            cls.form = None

    def _create_intake(self, **kwargs):
        """Helper to create intake with defaults."""
        vals = {"partner_id": self.supplier.id}
        if self.polymer:
            vals["polymer_id"] = self.polymer.id
        if self.form:
            vals["form_id"] = self.form.id
        vals.update(kwargs)
        return self.Intake.create(vals)

    def _create_match_result(self, intake=None, **kwargs):
        """Helper to create match result with defaults."""
        if intake is None:
            intake = self._create_intake()
        vals = {
            "intake_id": intake.id,
            "buyer_partner_id": self.buyer.id,
            "score": 85.0,
            "confidence": 90.0,
            "run_id": f"RUN-{intake.id}",
        }
        vals.update(kwargs)
        return self.MatchResult.create(vals)

    # ═══════════════════════════════════════════════════════════════════
    # Match Result Tests
    # ═══════════════════════════════════════════════════════════════════

    def test_match_result_creation(self):
        """Test basic match result creation with all required fields."""
        intake = self._create_intake()
        result = self._create_match_result(intake)

        self.assertTrue(result.exists())
        self.assertEqual(result.intake_id, intake)
        self.assertEqual(result.buyer_partner_id, self.buyer)
        self.assertEqual(result.score, 85.0)
        self.assertEqual(result.state, "pending")

    def test_match_result_display_name(self):
        """Test computed display_name includes intake, buyer, and score."""
        result = self._create_match_result()
        self.assertIn(self.buyer.name, result.display_name)
        self.assertIn("85", result.display_name)

    def test_match_result_accept_workflow(self):
        """Test accepting a pending match result."""
        result = self._create_match_result()
        self.assertEqual(result.state, "pending")

        result.action_accept()

        self.assertEqual(result.state, "accepted")
        self.assertEqual(result.reviewed_by, self.env.user)
        self.assertTrue(result.reviewed_date)

    def test_match_result_reject_workflow(self):
        """Test rejecting a pending match result."""
        result = self._create_match_result()
        result.action_reject()

        self.assertEqual(result.state, "rejected")
        self.assertEqual(result.reviewed_by, self.env.user)

    def test_match_result_cannot_accept_non_pending(self):
        """Test that only pending results can be accepted."""
        result = self._create_match_result()
        result.action_accept()

        with self.assertRaises(UserError):
            result.action_accept()

    def test_match_result_cannot_reject_non_pending(self):
        """Test that only pending results can be rejected."""
        result = self._create_match_result()
        result.action_reject()

        with self.assertRaises(UserError):
            result.action_reject()

    def test_match_result_score_breakdown_json(self):
        """Test score_breakdown JSON field stores structured data."""
        breakdown = {
            "polymer_match": 95.0,
            "form_match": 80.0,
            "location_score": 70.0,
        }
        result = self._create_match_result(score_breakdown=breakdown)

        self.assertEqual(result.score_breakdown["polymer_match"], 95.0)
        self.assertEqual(result.score_breakdown["form_match"], 80.0)

    def test_match_result_denormalized_fields(self):
        """Test denormalized intake fields are stored correctly."""
        intake = self._create_intake()
        result = self._create_match_result(intake)

        self.assertEqual(result.intake_partner_id, self.supplier)
        if self.polymer:
            self.assertEqual(result.intake_polymer, self.polymer.name)

    # ═══════════════════════════════════════════════════════════════════
    # Match Exclusion Tests
    # ═══════════════════════════════════════════════════════════════════

    def test_exclusion_creation(self):
        """Test creating a buyer-supplier exclusion."""
        exclusion = self.MatchExclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer.id,
                "reason": "qc_dispute",
                "exclusion_type": "permanent",
            }
        )

        self.assertTrue(exclusion.exists())
        self.assertTrue(exclusion.active)

    def test_exclusion_temporary_requires_expiry(self):
        """Test temporary exclusions require an expiry date."""
        with self.assertRaises(ValidationError):
            self.MatchExclusion.create(
                {
                    "supplier_partner_id": self.supplier.id,
                    "buyer_partner_id": self.buyer.id,
                    "reason": "quality_declined",
                    "exclusion_type": "temporary",
                }
            )

    def test_exclusion_same_partner_blocked(self):
        """Test supplier and buyer cannot be the same partner."""
        with self.assertRaises(ValidationError):
            self.MatchExclusion.create(
                {
                    "supplier_partner_id": self.supplier.id,
                    "buyer_partner_id": self.supplier.id,
                    "reason": "other",
                    "exclusion_type": "permanent",
                }
            )

    def test_is_pair_excluded_permanent(self):
        """Test is_pair_excluded returns True for permanent exclusions."""
        self.MatchExclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer.id,
                "reason": "legal_hold",
                "exclusion_type": "permanent",
            }
        )

        self.assertTrue(self.MatchExclusion.is_pair_excluded(self.supplier.id, self.buyer.id))

    def test_is_pair_excluded_temporary_active(self):
        """Test is_pair_excluded returns True for active temporary exclusions."""
        from datetime import date, timedelta

        self.MatchExclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer.id,
                "reason": "payment_issue",
                "exclusion_type": "temporary",
                "expiry_date": date.today() + timedelta(days=30),
            }
        )

        self.assertTrue(self.MatchExclusion.is_pair_excluded(self.supplier.id, self.buyer.id))

    def test_get_excluded_buyer_ids(self):
        """Test get_excluded_buyer_ids returns correct buyer list."""
        self.MatchExclusion.create(
            {
                "supplier_partner_id": self.supplier.id,
                "buyer_partner_id": self.buyer.id,
                "reason": "logistics_issue",
                "exclusion_type": "permanent",
            }
        )

        excluded = self.MatchExclusion.get_excluded_buyer_ids(self.supplier.id)
        self.assertIn(self.buyer.id, excluded)

    def test_exclusion_reason_selection(self):
        """Test all valid exclusion reasons can be set."""
        reasons = ["qc_dispute", "legal_hold", "quality_declined", "payment_issue", "logistics_issue", "other"]

        for reason in reasons:
            exclusion = self.MatchExclusion.create(
                {
                    "supplier_partner_id": self.supplier.id,
                    "buyer_partner_id": self.Partner.create({"name": f"Buyer {reason}"}).id,
                    "reason": reason,
                    "exclusion_type": "permanent",
                }
            )
            self.assertEqual(exclusion.reason, reason)

    # ═══════════════════════════════════════════════════════════════════
    # Integration Tests
    # ═══════════════════════════════════════════════════════════════════

    def test_match_result_with_facility(self):
        """Test match result can link to specific buyer facility."""
        result = self._create_match_result(buyer_facility_id=self.buyer_facility.id)

        self.assertEqual(result.buyer_facility_id, self.buyer_facility)
        self.assertEqual(result.buyer_facility_id.parent_id, self.buyer)

    def test_multiple_match_results_per_intake(self):
        """Test multiple buyers can match to same intake."""
        intake = self._create_intake()
        buyer2 = self.Partner.create({"name": "Second Buyer"})

        result1 = self._create_match_result(intake, score=90.0)
        result2 = self._create_match_result(
            intake,
            buyer_partner_id=buyer2.id,
            score=75.0,
            run_id=f"RUN-{intake.id}-2",
        )

        self.assertEqual(result1.intake_id, result2.intake_id)
        self.assertNotEqual(result1.buyer_partner_id, result2.buyer_partner_id)
