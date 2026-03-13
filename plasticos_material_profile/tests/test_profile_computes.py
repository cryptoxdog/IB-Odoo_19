"""
Test material profile computed fields.

- polymer/form/color computed Selection fields
- partner counts (po_line_count, so_line_count)
- company_id related field
"""

import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestProfileComputes(PlasticosTestCase):
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
        cls._polymer_code = "HDPE"
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "High Density Polyethylene",
                "code": cls._polymer_code,
            }
        )
        cls._form_code = "PELLETS"
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Pellets",
                "code": cls._form_code,
            }
        )
        cls._color_code = "NATURAL"
        cls.color = cls.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": cls._color_code,
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
    # Computed Selection Field Tests
    # ═══════════════════════════════════════════════════════════

    def test_polymer_code_computed(self):
        """Polymer Selection field should be computed from polymer_id.code."""
        profile = self._create_profile()
        self.assertEqual(profile.polymer, self._polymer_code)

    def test_form_code_computed(self):
        """Form Selection field should be computed from form_id.code."""
        profile = self._create_profile()
        self.assertEqual(profile.form, self._form_code)

    def test_color_code_computed(self):
        """Color Selection field should be computed from color_id.code."""
        profile = self._create_profile(color_id=self.color.id)
        self.assertEqual(profile.color, self._color_code)

    def test_color_code_false_when_no_color(self):
        """Color Selection field should be False when no color_id."""
        profile = self._create_profile()
        self.assertFalse(profile.color)

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

    def test_company_id_computed_from_partner_parent(self):
        """Company ID should be computed from partner's parent_id."""
        profile = self._create_profile()
        # company_id is related to partner_id.parent_id
        self.assertEqual(profile.company_id, self.parent_company)

    # ═══════════════════════════════════════════════════════════
    # Quality Metrics Tests
    # ═══════════════════════════════════════════════════════════

    def test_melt_flow_index_stored(self):
        """Melt flow index should be stored correctly."""
        profile = self._create_profile(melt_flow_index=12.5)
        self.assertEqual(profile.melt_flow_index, 12.5)

    def test_density_stored(self):
        """Density should be stored correctly."""
        profile = self._create_profile(density=0.945)
        self.assertEqual(profile.density, 0.945)

    def test_contamination_percent_stored(self):
        """Contamination percent should be stored correctly."""
        profile = self._create_profile(contamination_percent=2.5)
        self.assertEqual(profile.contamination_percent, 2.5)

    # ═══════════════════════════════════════════════════════════
    # Boolean Flag Tests
    # ═══════════════════════════════════════════════════════════

    def test_has_metal_default_false(self):
        """has_metal should default to False."""
        profile = self._create_profile()
        self.assertFalse(profile.has_metal)

    def test_is_metalized_default_false(self):
        """is_metalized should default to False."""
        profile = self._create_profile()
        self.assertFalse(profile.is_metalized)

    def test_has_fr_default_false(self):
        """has_fr should default to False."""
        profile = self._create_profile()
        self.assertFalse(profile.has_fr)
