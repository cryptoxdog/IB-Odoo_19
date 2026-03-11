import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestMaterialProfileComputes(PlasticosTestCase):
    """Covers @api.depends computed fields on material profile."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        # Partner must have parent_id to satisfy _check_partner_is_facility constraint
        cls.parent_company = cls.env["res.partner"].create({"name": "Parent Co C", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Facility C",
                "parent_id": cls.parent_company.id,
            }
        )
        cls.polymer = cls.env["plasticos.polymer"].create({"name": "PET", "code": _unique_code("PET")})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Bottle", "code": _unique_code("BOT")})

    def _create_profile(self, **vals):
        base = {
            "partner_id": self.partner.id,
            "polymer_id": self.polymer.id,
            "form_id": self.form.id,
        }
        base.update(vals)
        return self.Profile.create(base)

    def test_display_name_computed_from_parts(self):
        profile = self._create_profile()
        self.assertTrue(profile.display_name)
        self.assertIn("PET", profile.display_name)
        self.assertIn("Bottle", profile.display_name)

    def test_full_description_includes_key_fields(self):
        profile = self._create_profile()
        if hasattr(profile, "full_description"):
            self.assertIn("PET", profile.full_description)
            self.assertIn("Bottle", profile.full_description)

    def test_partner_profile_counts_computed(self):
        # First profile
        p1 = self._create_profile()
        self.partner.invalidate_recordset()
        if hasattr(self.partner, "material_profile_count"):
            self.assertGreaterEqual(self.partner.material_profile_count, 1)

        # Second profile for same partner should bump count
        p2 = self._create_profile(form_id=self.form.copy({"code": _unique_code("BOT")}).id)
        self.partner.invalidate_recordset()
        if hasattr(self.partner, "material_profile_count"):
            self.assertGreaterEqual(self.partner.material_profile_count, 2)
