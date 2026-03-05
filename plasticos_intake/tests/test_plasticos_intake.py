# tests/test_plasticos_intake.py

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos")
class TestPlasticosIntake(TransactionCase):
    """Comprehensive test suite for plasticos.intake model"""

    @classmethod
    def setUpClass(cls):
        """Setup test data once for all tests"""
        super().setUpClass()

        # Create test partner
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier",
                "is_company": True,
                "supplier_rank": 1,
            }
        )

        # Create test material types
        cls.material_pet = cls.env["plasticos.material"].create(
            {
                "name": "PET",
                "code": "PET",
            }
        )

        # Create test sequence
        cls.sequence = cls.env["ir.sequence"].create(
            {
                "name": "Test Intake Sequence",
                "code": "plasticos.intake",
                "prefix": "INT/%(year)s/",
                "padding": 5,
            }
        )

    def _create_intake(self, **kwargs):
        """Helper to create intake with defaults"""
        vals = {
            "partner_id": self.partner.id,
            "material_type": "PET",
            "quantity_per_load_lbs": 1000,
        }
        vals.update(kwargs)
        return self.env["plasticos.intake"].create(vals)

    # ========================================================================
    # CREATION TESTS
    # ========================================================================

    def test_create_with_sequence_generation(self):
        """Test intake creation auto-generates sequence"""
        intake = self._create_intake()

        self.assertTrue(intake.exists())
        self.assertNotEqual(intake.name, "/")
        self.assertRegex(intake.name, r"^INT/\d{4}/\d{5}$")

    def test_create_bulk_unique_sequences(self):
        """Test bulk creation generates unique sequences"""
        intakes = self.env["plasticos.intake"].create(
            [
                {
                    "partner_id": self.partner.id,
                    "material_type": "PET",
                    "quantity_per_load_lbs": 1000 + i,
                }
                for i in range(50)
            ]
        )

        names = intakes.mapped("name")
        self.assertEqual(len(names), 50)
        self.assertEqual(len(set(names)), 50, "All sequences should be unique")

    def test_create_missing_required_field_raises_error(self):
        """Test creating intake without required fields fails"""
        with self.assertRaises(ValidationError):
            self.env["plasticos.intake"].create(
                {
                    "partner_id": self.partner.id,
                    # Missing quantity_per_load_lbs
                }
            )

    def test_create_with_invalid_quantity_raises_error(self):
        """Test quantity validation constraint"""
        with self.assertRaises(ValidationError):
            self._create_intake(quantity_per_load_lbs=0)

        with self.assertRaises(ValidationError):
            self._create_intake(quantity_per_load_lbs=-100)

    # ========================================================================
    # STATE MACHINE TESTS
    # ========================================================================

    def test_state_draft_to_confirmed(self):
        """Test draft → confirmed transition"""
        intake = self._create_intake()

        self.assertEqual(intake.state, "draft")
        self.assertTrue(intake.can_confirm)

        intake.action_confirm()

        self.assertEqual(intake.state, "confirmed")
        self.assertFalse(intake.can_confirm)
        self.assertTrue(intake.can_approve)

    def test_state_confirmed_to_approved(self):
        """Test confirmed → approved transition"""
        intake = self._create_intake()
        intake.action_confirm()

        intake.action_approve()

        self.assertEqual(intake.state, "approved")
        self.assertTrue(intake.approved_date)
        self.assertEqual(intake.approved_by, self.env.user)

    def test_state_cannot_skip_workflow_steps(self):
        """Test cannot skip workflow states"""
        intake = self._create_intake()

        # Try to approve from draft (should fail)
        with self.assertRaises(UserError):
            intake.action_approve()

        self.assertEqual(intake.state, "draft", "State should remain draft")

    def test_state_cancel_from_any_state(self):
        """Test cancel action available from any state"""
        for initial_state in ["draft", "confirmed", "approved"]:
            intake = self._create_intake()
            intake.state = initial_state

            intake.action_cancel()

            self.assertEqual(intake.state, "cancelled")

    # ========================================================================
    # COMPUTE FIELD TESTS
    # ========================================================================

    def test_compute_profile_summary_with_facilities(self):
        """Test profile_summary computes correctly"""
        # Create partner with facilities
        partner = self.env["res.partner"].create(
            {
                "name": "Supplier With Facilities",
                "is_company": True,
            }
        )

        facilities = self.env["res.partner"].create(
            [
                {
                    "name": f"Facility {i}",
                    "parent_id": partner.id,
                    "monthly_capacity_lbs": 5000 * i,
                }
                for i in range(1, 4)
            ]
        )

        intake = self._create_intake(partner_id=partner.id)

        summary = intake.profile_summary
        self.assertEqual(summary["total_facilities"], 3)
        self.assertEqual(summary["total_capacity"], 5000 + 10000 + 15000)

    def test_compute_profile_summary_with_no_facilities(self):
        """Test profile_summary handles partners without facilities"""
        intake = self._create_intake()

        summary = intake.profile_summary
        self.assertEqual(summary["total_facilities"], 0)
        self.assertEqual(summary["total_capacity"], 0)

    # ========================================================================
    # CONSTRAINT TESTS
    # ========================================================================

    def test_constraint_unique_name_per_company(self):
        """Test intake names must be unique per company"""
        intake1 = self._create_intake()

        # Try to create duplicate
        with self.assertRaises(ValidationError):
            self.env["plasticos.intake"].create(
                {
                    "name": intake1.name,  # Same name
                    "partner_id": self.partner.id,
                    "material_type": "HDPE",
                    "quantity_per_load_lbs": 2000,
                }
            )

    def test_constraint_quantity_positive(self):
        """Test quantity must be positive"""
        with self.assertRaises(ValidationError) as cm:
            self._create_intake(quantity_per_load_lbs=-500)

        self.assertIn("positive", str(cm.exception).lower())

    # ========================================================================
    # ONCHANGE TESTS
    # ========================================================================

    def test_onchange_partner_updates_contact_info(self):
        """Test partner selection updates contact fields"""
        intake = self.env["plasticos.intake"].new(
            {
                "material_type": "PET",
                "quantity_per_load_lbs": 1000,
            }
        )

        intake.partner_id = self.partner
        intake._onchange_partner_id()

        # Verify fields populated
        self.assertTrue(intake.partner_email or intake.partner_phone, "Contact info should be populated")

    # ========================================================================
    # ACTION TESTS
    # ========================================================================

    def test_action_view_offers_returns_correct_action(self):
        """Test view offers button returns proper action"""
        intake = self._create_intake()

        # Create test offers
        self.env["plasticos.offer"].create(
            [
                {
                    "intake_id": intake.id,
                    "buyer_id": self.env.ref("base.res_partner_2").id,
                    "offer_price": 100 * i,
                }
                for i in range(1, 4)
            ]
        )

        action = intake.action_view_offers()

        self.assertEqual(action["res_model"], "plasticos.offer")
        self.assertEqual(action["domain"], [("intake_id", "=", intake.id)])
        self.assertEqual(action["context"]["default_intake_id"], intake.id)

    # ========================================================================
    # COPY/DUPLICATE TESTS
    # ========================================================================

    def test_copy_regenerates_sequence(self):
        """Test duplicating intake creates new sequence"""
        original = self._create_intake()
        duplicate = original.copy()

        self.assertNotEqual(original.name, duplicate.name)
        self.assertRegex(duplicate.name, r"^INT/\d{4}/\d{5}$")
        self.assertEqual(duplicate.state, "draft")

    # ========================================================================
    # UNLINK/DELETE TESTS
    # ========================================================================

    def test_unlink_draft_allowed(self):
        """Test deleting draft intake is allowed"""
        intake = self._create_intake()

        intake.unlink()

        self.assertFalse(intake.exists())

    def test_unlink_confirmed_blocked(self):
        """Test deleting confirmed intake is blocked"""
        intake = self._create_intake()
        intake.action_confirm()

        with self.assertRaises(UserError):
            intake.unlink()

        self.assertTrue(intake.exists())

    # ========================================================================
    # SEARCH TESTS
    # ========================================================================

    def test_search_by_partner(self):
        """Test searching intakes by partner"""
        intake1 = self._create_intake(partner_id=self.partner.id)

        other_partner = self.env["res.partner"].create({"name": "Other"})
        intake2 = self._create_intake(partner_id=other_partner.id)

        results = self.env["plasticos.intake"].search([("partner_id", "=", self.partner.id)])

        self.assertIn(intake1, results)
        self.assertNotIn(intake2, results)

    # ========================================================================
    # ACCESS RIGHTS TESTS
    # ========================================================================

    def test_access_rights_user_can_create(self):
        """Test regular user can create intakes"""
        user = self.env["res.users"].create(
            {
                "name": "Test User",
                "login": "testuser",
                "group_ids": [(6, 0, [self.env.ref("plasticos_intake.group_intake_user").id])],
            }
        )

        intake = (
            self.env["plasticos.intake"]
            .with_user(user)
            .create(
                {
                    "partner_id": self.partner.id,
                    "material_type": "PET",
                    "quantity_per_load_lbs": 1000,
                }
            )
        )

        self.assertTrue(intake.exists())

    def test_access_rights_user_cannot_delete_confirmed(self):
        """Test regular user cannot delete confirmed intakes"""
        user = self.env["res.users"].create(
            {
                "name": "Test User",
                "login": "testuser2",
                "group_ids": [(6, 0, [self.env.ref("plasticos_intake.group_intake_user").id])],
            }
        )

        intake = self._create_intake()
        intake.action_confirm()

        with self.assertRaises(UserError):
            intake.with_user(user).unlink()
