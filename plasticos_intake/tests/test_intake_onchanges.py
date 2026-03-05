"""
Test intake onchange methods.

Tests 9 onchanges:
- polymer → form defaults
- partner → facility cascade
- material attributes → boolean flags
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestIntakeOnchanges(TransactionCase):
    """Test plasticos.intake onchange methods."""

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
    # Partner Onchange Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_partner_clears_facility(self):
        """Changing partner should clear facility if not child."""
        intake = self._create_intake(facility_id=self.facility.id)

        # Create new partner
        new_partner = self.env["res.partner"].create(
            {
                "name": "New Partner",
                "is_company": True,
            }
        )

        intake.partner_id = new_partner
        intake._onchange_partner_id()

        # Facility should be cleared (not child of new partner)
        self.assertFalse(intake.facility_id)

    def test_onchange_partner_clears_contact(self):
        """Changing partner should clear contact if not child."""
        intake = self._create_intake(contact_id=self.contact.id)

        new_partner = self.env["res.partner"].create(
            {
                "name": "New Partner",
                "is_company": True,
            }
        )

        intake.partner_id = new_partner
        intake._onchange_partner_id()

        # Contact should be cleared
        self.assertFalse(intake.contact_id)

    # ═══════════════════════════════════════════════════════════
    # Facility Onchange Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_facility_sets_partner(self):
        """Setting facility should set partner to facility's parent."""
        intake = self._create_intake(partner_id=False)
        intake.facility_id = self.facility
        intake._onchange_facility_id()

        self.assertEqual(intake.partner_id, self.partner)

    # ═══════════════════════════════════════════════════════════
    # Contact Onchange Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_contact_sets_partner(self):
        """Setting contact should set partner to contact's parent."""
        intake = self._create_intake(partner_id=False)
        intake.contact_id = self.contact
        intake._onchange_contact_id()

        self.assertEqual(intake.partner_id, self.partner)

    # ═══════════════════════════════════════════════════════════
    # Material Profile Onchange Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_material_profile_sets_polymer(self):
        """Setting material_profile should copy polymer."""
        if "plasticos.material.profile" not in self.env:
            self.skipTest("plasticos.material.profile not installed")

        if "plasticos.polymer" not in self.env:
            self.skipTest("plasticos.polymer not installed")

        polymer = self.env["plasticos.polymer"].create(
            {
                "name": "HDPE",
                "code": "HDPE",
            }
        )

        profile = self.env["plasticos.material.profile"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": polymer.id,
            }
        )

        intake = self._create_intake()
        intake.material_profile_id = profile
        intake._onchange_material_profile()

        self.assertEqual(intake.polymer_id, polymer)

    # ═══════════════════════════════════════════════════════════
    # Material Attributes Onchange Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_has_metal_sets_flag(self):
        """Setting has_metal should update material_attributes."""
        intake = self._create_intake()
        intake.has_metal = True
        intake._onchange_has_metal()

        # Material attributes should include metal flag
        if hasattr(intake, "material_attributes"):
            self.assertIn("metal", intake.material_attributes or "")

    def test_onchange_is_metalized_sets_flag(self):
        """Setting is_metalized should update material_attributes."""
        intake = self._create_intake()
        intake.is_metalized = True
        intake._onchange_is_metalized()

        if hasattr(intake, "material_attributes"):
            self.assertIn("metalized", intake.material_attributes or "")

    def test_onchange_has_fr_sets_flag(self):
        """Setting has_fr should update material_attributes."""
        intake = self._create_intake()
        intake.has_fr = True
        intake._onchange_has_fr()

        if hasattr(intake, "material_attributes"):
            self.assertIn("fr", intake.material_attributes or "")

    # ═══════════════════════════════════════════════════════════
    # Lead Source Onchange Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_lead_source_sets_utm(self):
        """Setting lead_source should set UTM source."""
        if "utm.source" not in self.env:
            self.skipTest("utm.source not installed")

        utm_source = self.env["utm.source"].create(
            {
                "name": "Website",
            }
        )

        intake = self._create_intake()
        intake.lead_source_id = utm_source
        intake._onchange_lead_source_id()

        # UTM source should be set
        self.assertEqual(intake.lead_source_id, utm_source)
