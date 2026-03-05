"""
Test facility profile constraints.

- density_min < density_max
- melt_index_min < melt_index_max
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFacilityConstraints(TransactionCase):
    """Test plasticos.facility.profile constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Facility",
                "is_company": True,
            }
        )

    def _create_facility(self, **kwargs):
        """Helper to create a facility profile."""
        vals = {
            "partner_id": self.partner.id,
        }
        vals.update(kwargs)
        return self.env["plasticos.facility.profile"].create(vals)

    def test_density_min_less_than_max(self):
        """density_min must be less than density_max."""
        facility = self._create_facility()

        with self.assertRaises(ValidationError):
            facility.write(
                {
                    "density_min": 1.0,
                    "density_max": 0.5,
                }
            )

    def test_density_valid_range(self):
        """Valid density range should be accepted."""
        facility = self._create_facility(
            density_min=0.90,
            density_max=0.96,
        )
        self.assertEqual(facility.density_min, 0.90)
        self.assertEqual(facility.density_max, 0.96)

    def test_melt_index_min_less_than_max(self):
        """melt_index_min must be less than melt_index_max."""
        facility = self._create_facility()

        with self.assertRaises(ValidationError):
            facility.write(
                {
                    "melt_index_min": 20.0,
                    "melt_index_max": 5.0,
                }
            )

    def test_melt_index_valid_range(self):
        """Valid melt index range should be accepted."""
        facility = self._create_facility(
            melt_index_min=5.0,
            melt_index_max=15.0,
        )
        self.assertEqual(facility.melt_index_min, 5.0)
        self.assertEqual(facility.melt_index_max, 15.0)

    def test_equal_min_max_allowed(self):
        """Equal min and max should be allowed (exact value)."""
        facility = self._create_facility(
            density_min=0.95,
            density_max=0.95,
        )
        self.assertEqual(facility.density_min, facility.density_max)
