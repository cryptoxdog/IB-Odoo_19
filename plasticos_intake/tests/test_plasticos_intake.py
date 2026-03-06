"""Tests for plasticos.intake model.

Target module: plasticos_intake
Target model:  plasticos.intake

Tests creation, sequence generation, constraints, and onchange behavior.
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "intake")
class TestPlasticosIntake(TransactionCase):
    """Test suite for plasticos.intake model."""

    @classmethod
    def setUpClass(cls):
        """Setup test data once for all tests."""
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

    def _create_intake(self, **kwargs):
        """Helper to create intake with defaults."""
        vals = {
            "partner_id": self.partner.id,
            "quantity_per_load_lbs": 40000,
        }
        vals.update(kwargs)
        return self.env["plasticos.intake"].create(vals)

    # ══════════════════════════════════════════════════════════
    # CREATION TESTS
    # ══════════════════════════════════════════════════════════

    def test_create_with_sequence_generation(self):
        """Test intake creation auto-generates sequence."""
        intake = self._create_intake()
        self.assertTrue(intake.exists())
        self.assertNotEqual(intake.name, "/")
        # Sequence format: INT-YY-NNNNN
        self.assertTrue(intake.name.startswith("INT-"))

    def test_create_bulk_unique_sequences(self):
        """Test bulk creation generates unique sequences."""
        intakes = self.env["plasticos.intake"].create(
            [
                {
                    "partner_id": self.partner.id,
                    "quantity_per_load_lbs": 40000 + i,
                }
                for i in range(10)
            ]
        )
        names = intakes.mapped("name")
        self.assertEqual(len(names), 10)
        self.assertEqual(len(set(names)), 10, "All sequences should be unique")

    def test_create_with_default_quantity(self):
        """Test intake uses default quantity_per_load_lbs."""
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.partner.id,
            }
        )
        self.assertEqual(intake.quantity_per_load_lbs, 40000)

    # ══════════════════════════════════════════════════════════
    # CONSTRAINT TESTS
    # ══════════════════════════════════════════════════════════

    def test_constraint_quantity_positive(self):
        """Test quantity must be positive."""
        with self.assertRaises(ValidationError):
            self._create_intake(quantity_per_load_lbs=0)

        with self.assertRaises(ValidationError):
            self._create_intake(quantity_per_load_lbs=-100)

    # ══════════════════════════════════════════════════════════
    # STATUS TESTS
    # ══════════════════════════════════════════════════════════

    def test_default_status_is_draft(self):
        """Test new intake starts in draft status."""
        intake = self._create_intake()
        self.assertEqual(intake.status, "draft")

    def test_status_can_be_changed(self):
        """Test status can be updated."""
        intake = self._create_intake()
        intake.status = "matched"
        self.assertEqual(intake.status, "matched")

    # ══════════════════════════════════════════════════════════
    # COMPUTED FIELD TESTS
    # ══════════════════════════════════════════════════════════

    def test_display_name_computed(self):
        """Test display_name is computed from name."""
        intake = self._create_intake()
        self.assertTrue(intake.display_name)
        # Display name should be set
        self.assertNotEqual(intake.display_name, "")

    def test_company_display_with_partner(self):
        """Test company_display shows partner name."""
        intake = self._create_intake()
        self.assertEqual(intake.company_display, self.partner.name)

    def test_company_display_with_pending_name(self):
        """Test company_display shows pending name when no partner."""
        intake = self.env["plasticos.intake"].create(
            {
                "quantity_per_load_lbs": 40000,
                "pending_company_name": "Pending Corp",
            }
        )
        self.assertIn("Pending Corp", intake.company_display)

    # ══════════════════════════════════════════════════════════
    # ONCHANGE TESTS
    # ══════════════════════════════════════════════════════════

    def test_onchange_partner_clears_facility(self):
        """Test changing partner clears facility_id."""
        intake = self.env["plasticos.intake"].new(
            {
                "partner_id": self.partner.id,
                "quantity_per_load_lbs": 40000,
            }
        )
        # Set a facility
        intake.facility_id = self.partner.id
        # Change partner
        new_partner = self.env["res.partner"].create(
            {
                "name": "New Partner",
                "is_company": True,
            }
        )
        intake.partner_id = new_partner
        intake._onchange_partner_id()
        # Facility should be auto-set to new partner (single facility case)
        self.assertEqual(intake.facility_id.id, new_partner.id)

    def test_onchange_partner_auto_selects_single_facility(self):
        """Test partner with single facility auto-selects it."""
        parent = self.env["res.partner"].create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        child = self.env["res.partner"].create(
            {
                "name": "Single Facility",
                "is_company": True,
                "parent_id": parent.id,
            }
        )
        intake = self.env["plasticos.intake"].new(
            {
                "quantity_per_load_lbs": 40000,
            }
        )
        intake.partner_id = parent
        intake._onchange_partner_id()
        self.assertEqual(intake.facility_id.id, child.id)

    # ══════════════════════════════════════════════════════════
    # COPY/DUPLICATE TESTS
    # ══════════════════════════════════════════════════════════

    def test_copy_regenerates_sequence(self):
        """Test duplicating intake creates new sequence."""
        original = self._create_intake()
        duplicate = original.copy()
        self.assertNotEqual(original.name, duplicate.name)
        self.assertTrue(duplicate.name.startswith("INT-"))

    # ══════════════════════════════════════════════════════════
    # SEARCH TESTS
    # ══════════════════════════════════════════════════════════

    def test_search_by_partner(self):
        """Test searching intakes by partner."""
        intake1 = self._create_intake(partner_id=self.partner.id)
        other_partner = self.env["res.partner"].create(
            {
                "name": "Other Partner",
                "is_company": True,
            }
        )
        intake2 = self._create_intake(partner_id=other_partner.id)

        results = self.env["plasticos.intake"].search([("partner_id", "=", self.partner.id)])
        self.assertIn(intake1, results)
        self.assertNotIn(intake2, results)

    def test_search_by_status(self):
        """Test searching intakes by status."""
        intake1 = self._create_intake()
        intake2 = self._create_intake()
        intake2.status = "matched"

        draft_intakes = self.env["plasticos.intake"].search([("status", "=", "draft")])
        self.assertIn(intake1, draft_intakes)
        self.assertNotIn(intake2, draft_intakes)

    # ══════════════════════════════════════════════════════════
    # MATCH COUNT TESTS
    # ══════════════════════════════════════════════════════════

    def test_match_count_starts_at_zero(self):
        """Test new intake has zero matches."""
        intake = self._create_intake()
        self.assertEqual(intake.match_count, 0)
        self.assertEqual(intake.selected_count, 0)
        self.assertEqual(intake.best_match_score, 0.0)
