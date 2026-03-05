"""
Test intake CRUD operations.

- create with partner+facility linkage
- display_name assembly
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntakeCRUD(TransactionCase):
    """Test plasticos.intake CRUD operations."""

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
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "Test Facility",
                "is_company": True,
                "parent_id": cls.partner.id,
            }
        )
        cls.contact = cls.env["res.partner"].create(
            {
                "name": "Test Contact",
                "is_company": False,
                "parent_id": cls.partner.id,
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
    # Create Tests
    # ═══════════════════════════════════════════════════════════

    def test_create_basic_intake(self):
        """Basic intake can be created with partner."""
        intake = self._create_intake()
        self.assertTrue(intake.id)
        self.assertEqual(intake.partner_id, self.partner)

    def test_create_with_facility(self):
        """Intake can be created with facility linkage."""
        intake = self._create_intake(facility_id=self.facility.id)
        self.assertEqual(intake.facility_id, self.facility)

    def test_create_with_contact(self):
        """Intake can be created with contact linkage."""
        intake = self._create_intake(contact_id=self.contact.id)
        self.assertEqual(intake.contact_id, self.contact)

    def test_create_generates_name(self):
        """Intake name should be auto-generated."""
        intake = self._create_intake()
        self.assertTrue(intake.name)

    # ═══════════════════════════════════════════════════════════
    # Display Name Tests
    # ═══════════════════════════════════════════════════════════

    def test_display_name_includes_partner(self):
        """Display name should include partner name."""
        intake = self._create_intake()
        self.assertIn(self.partner.name, intake.display_name)

    def test_display_name_includes_polymer(self):
        """Display name should include polymer if set."""
        # Create polymer if model exists
        if "plasticos.polymer" in self.env:
            polymer = self.env["plasticos.polymer"].create(
                {
                    "name": "HDPE",
                    "code": "HDPE",
                }
            )
            intake = self._create_intake(polymer_id=polymer.id)
            self.assertIn("HDPE", intake.display_name)

    # ═══════════════════════════════════════════════════════════
    # Status Tests
    # ═══════════════════════════════════════════════════════════

    def test_default_status_is_new(self):
        """New intake should have status 'new'."""
        intake = self._create_intake()
        self.assertEqual(intake.status, "new")

    def test_status_transitions(self):
        """Intake status can transition through workflow."""
        intake = self._create_intake()

        # Transition to offer_sent
        intake.action_send_offer()
        self.assertEqual(intake.status, "offer_sent")

        # Transition to processing
        intake.action_mark_processing()
        self.assertEqual(intake.status, "processing")
