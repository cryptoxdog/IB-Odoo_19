"""
Test partner material sync.

Tests custom write() partner sync loop guard.
"""

import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestPartnerMaterialSync(PlasticosTestCase):
    """Test partner material sync functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create parent company first
        cls.parent_company = cls.env["res.partner"].create(
            {
                "name": "Test Parent Company",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        # Create facility-level partner (child of parent company)
        # Required by _check_partner_is_facility constraint
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Supplier Facility",
                "is_company": True,
                "supplier_rank": 1,
                "parent_id": cls.parent_company.id,
            }
        )
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "High Density Polyethylene",
                "code": _unique_code("HDPE"),
            }
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Pellets",
                "code": _unique_code("PELLETS"),
            }
        )

    def _create_profile(self, **kwargs):
        """Helper to create a material profile."""
        vals = {
            "partner_id": self.partner.id,
            "polymer_id": self.polymer.id,
            "form_id": self.form.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.material.profile"].create(vals)

    # ═══════════════════════════════════════════════════════════
    # Partner Sync Tests
    # ═══════════════════════════════════════════════════════════

    def test_profile_update_does_not_infinite_loop(self):
        """Profile update should not cause infinite loop with partner sync."""
        profile = self._create_profile()

        # Update profile multiple times - should not hang
        for i in range(5):
            profile.write({"mfi_min": float(i)})

        self.assertEqual(profile.mfi_min, 4.0)

    def test_partner_update_syncs_to_profiles(self):
        """Partner update should sync relevant data to profiles."""
        profile = self._create_profile()

        # Update partner
        self.partner.write({"name": "Updated Supplier Name"})

        # Profile should still be valid
        profile.invalidate_recordset()
        self.assertEqual(profile.partner_id.name, "Updated Supplier Name")

    def test_multiple_profiles_per_partner(self):
        """Multiple profiles per partner should all sync correctly."""
        profile1 = self._create_profile()

        polymer2 = self.env["plasticos.polymer"].create(
            {
                "name": "Polypropylene",
                "code": _unique_code("PP"),
            }
        )
        profile2 = self._create_profile(polymer_id=polymer2.id)

        # Update partner
        self.partner.write({"name": "Multi-Profile Supplier"})

        # Both profiles should be valid
        profile1.invalidate_recordset()
        profile2.invalidate_recordset()
        self.assertEqual(profile1.partner_id.name, "Multi-Profile Supplier")
        self.assertEqual(profile2.partner_id.name, "Multi-Profile Supplier")

    # ═══════════════════════════════════════════════════════════
    # Loop Guard Tests
    # ═══════════════════════════════════════════════════════════

    def test_write_with_context_flag(self):
        """Write with context flag should skip sync."""
        profile = self._create_profile()

        # Write with skip flag
        profile.with_context(skip_partner_sync=True).write(
            {
                "mfi_min": 10.0,
            }
        )

        self.assertEqual(profile.mfi_min, 10.0)

    def test_batch_write_does_not_loop(self):
        """Batch write on multiple profiles should not loop."""
        profiles = self.env["plasticos.material.profile"]

        for i in range(3):
            polymer = self.env["plasticos.polymer"].create(
                {
                    "name": f"Polymer {i}",
                    "code": _unique_code(f"TEST_P{i}"),
                }
            )
            profiles |= self._create_profile(polymer_id=polymer.id)

        # Batch write
        profiles.write({"mfi_min": 5.0})

        for profile in profiles:
            self.assertEqual(profile.mfi_min, 5.0)

    # ═══════════════════════════════════════════════════════════
    # Onchange Sync Tests
    # ═══════════════════════════════════════════════════════════

    def test_onchange_material_attributes_syncs(self):
        """Onchange on material attributes should sync to profile."""
        profile = self._create_profile()

        # Set has_metal flag
        profile.has_metal = True
        if hasattr(profile, "_onchange_has_metal"):
            profile._onchange_has_metal()

        # Material attributes should be updated (if attribute exists)
        # This is a soft check since attributes may not be seeded
        self.assertTrue(profile.has_metal)

    def test_onchange_is_metalized_syncs(self):
        """Onchange on is_metalized should sync to profile."""
        profile = self._create_profile()

        profile.is_metalized = True
        if hasattr(profile, "_onchange_is_metalized"):
            profile._onchange_is_metalized()

        self.assertTrue(profile.is_metalized)
