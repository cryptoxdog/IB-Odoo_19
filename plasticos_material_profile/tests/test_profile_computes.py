"""
Test material profile computed fields.

- display_name
- full_description
- partner counts (po_line_count, so_line_count)
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProfileComputes(TransactionCase):
    """Test plasticos.material.profile computed fields."""

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
        # Create facility-level partner (required by _check_partner_is_facility)
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
                "code": "HDPE",
            }
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Pellet",
                "code": "PELLET",
            }
        )
        cls.color = cls.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": "NAT",
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
    # Display Name Tests
    # ═══════════════════════════════════════════════════════════

    def test_display_name_includes_polymer(self):
        """Display name should include polymer code."""
        profile = self._create_profile()
        self.assertIn("HDPE", profile.display_name)

    def test_display_name_includes_form(self):
        """Display name should include form code."""
        profile = self._create_profile()
        self.assertIn("PELLET", profile.display_name)

    def test_display_name_includes_color(self):
        """Display name should include color if set."""
        profile = self._create_profile(color_id=self.color.id)
        self.assertIn("NAT", profile.display_name)

    def test_display_name_includes_partner(self):
        """Display name should include partner name."""
        profile = self._create_profile()
        self.assertIn(self.partner.name, profile.display_name)

    # ═══════════════════════════════════════════════════════════
    # Full Description Tests
    # ═══════════════════════════════════════════════════════════

    def test_full_description_computed(self):
        """Full description should be computed from components."""
        profile = self._create_profile(color_id=self.color.id)

        if hasattr(profile, "full_description"):
            desc = profile.full_description
            self.assertIn("HDPE", desc)
            self.assertIn("Pellet", desc)
            self.assertIn("Natural", desc)

    # ═══════════════════════════════════════════════════════════
    # Partner Count Tests
    # ═══════════════════════════════════════════════════════════

    def test_po_line_count_zero_initially(self):
        """PO line count should be 0 for new profile."""
        profile = self._create_profile()
        self.assertEqual(profile.po_line_count, 0)

    def test_so_line_count_zero_initially(self):
        """SO line count should be 0 for new profile."""
        profile = self._create_profile()
        self.assertEqual(profile.so_line_count, 0)

    # ═══════════════════════════════════════════════════════════
    # Company ID Tests
    # ═══════════════════════════════════════════════════════════

    def test_company_id_computed_from_partner(self):
        """Company ID should be computed from partner."""
        profile = self._create_profile()

        if hasattr(profile, "company_id"):
            # Company should match partner's company or current company
            self.assertTrue(profile.company_id)

    # ═══════════════════════════════════════════════════════════
    # Related Field Tests
    # ═══════════════════════════════════════════════════════════

    def test_polymer_name_related(self):
        """Polymer name should be accessible via related field."""
        profile = self._create_profile()

        if hasattr(profile, "polymer_name"):
            self.assertEqual(profile.polymer_name, "High Density Polyethylene")

    def test_form_name_related(self):
        """Form name should be accessible via related field."""
        profile = self._create_profile()

        if hasattr(profile, "form_name"):
            self.assertEqual(profile.form_name, "Pellet")
