"""
Test material profile CRUD operations.

- create profile with polymer+form+partner
- unique triple constraint
"""

import uuid

from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestProfileCRUD(PlasticosTestCase):
    """Test plasticos.material.profile CRUD operations."""

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
                "code": _unique_code("HDPE"),
            }
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Pellets",
                "code": _unique_code("PELLETS"),
            }
        )
        cls.color = cls.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": _unique_code("NATURAL"),
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
    # Create Tests
    # ═══════════════════════════════════════════════════════════

    def test_create_basic_profile(self):
        """Basic profile can be created with polymer+form+partner."""
        profile = self._create_profile()
        self.assertTrue(profile.id)
        self.assertEqual(profile.partner_id, self.partner)
        self.assertEqual(profile.polymer_id, self.polymer)
        self.assertEqual(profile.form_id, self.form)

    def test_create_profile_with_color(self):
        """Profile can be created with color."""
        profile = self._create_profile(color_id=self.color.id)
        self.assertEqual(profile.color_id, self.color)

    def test_create_profile_with_quality_metrics(self):
        """Profile can be created with quality metrics."""
        profile = self._create_profile(
            melt_flow_index=7.5,
            density=0.95,
            contamination_percent=0.5,
        )
        self.assertEqual(profile.melt_flow_index, 7.5)
        self.assertEqual(profile.density, 0.95)
        self.assertEqual(profile.contamination_percent, 0.5)

    # ═══════════════════════════════════════════════════════════
    # Unique Triple Constraint Tests
    # ═══════════════════════════════════════════════════════════

    def test_unique_partner_polymer_form_constraint(self):
        """Profile must be unique per partner+polymer+form combination."""
        self._create_profile()

        # Try to create duplicate
        with self.assertRaises((ValidationError, UserError, IntegrityError)):
            with self.env.cr.savepoint():
                self._create_profile()

    def test_different_partner_same_polymer_form_allowed(self):
        """Different partner with same polymer+form should be allowed."""
        self._create_profile()

        partner2 = self.env["res.partner"].create(
            {
                "name": "Test Supplier 2 Facility",
                "is_company": True,
                "parent_id": self.parent_company.id,
            }
        )

        profile2 = self._create_profile(partner_id=partner2.id)
        self.assertTrue(profile2.id)

    def test_same_partner_different_polymer_allowed(self):
        """Same partner with different polymer should be allowed."""
        self._create_profile()

        polymer2 = self.env["plasticos.polymer"].create(
            {
                "name": "Polypropylene",
                "code": _unique_code("PP"),
            }
        )

        profile2 = self._create_profile(polymer_id=polymer2.id)
        self.assertTrue(profile2.id)

    def test_same_partner_different_form_allowed(self):
        """Same partner with different form should be allowed."""
        self._create_profile()

        form2 = self.env["plasticos.material.form"].create(
            {
                "name": "Flake",
                "code": _unique_code("FLAKE"),
            }
        )

        profile2 = self._create_profile(form_id=form2.id)
        self.assertTrue(profile2.id)

    # ═══════════════════════════════════════════════════════════
    # Search Tests
    # ═══════════════════════════════════════════════════════════

    def test_search_by_partner(self):
        """Profiles can be searched by partner."""
        profile = self._create_profile()

        found = self.env["plasticos.material.profile"].search(
            [
                ("partner_id", "=", self.partner.id),
            ]
        )
        self.assertIn(profile, found)

    def test_search_by_polymer(self):
        """Profiles can be searched by polymer."""
        profile = self._create_profile()

        found = self.env["plasticos.material.profile"].search(
            [
                ("polymer_id", "=", self.polymer.id),
            ]
        )
        self.assertIn(profile, found)
