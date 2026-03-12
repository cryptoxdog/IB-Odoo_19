"""
Test facility profile CRUD operations.

- create profile
- unique partner constraint
- partner sync
"""

from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFacilityCRUD(PlasticosTestCase):
    """Test plasticos.facility.profile CRUD operations."""

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

    def test_create_facility(self):
        """Facility profile can be created."""
        facility = self._create_facility()
        self.assertTrue(facility.id)

    def test_unique_partner_constraint(self):
        """Facility profile must be unique per partner."""
        self._create_facility()

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_facility_profile (partner_id)
                VALUES (%s)
            """,
                (self.partner.id,),
            )

    def test_different_partners_allowed(self):
        """Different partners can have facility profiles."""
        self._create_facility()

        partner2 = self.env["res.partner"].create(
            {
                "name": "Test Facility 2",
                "is_company": True,
            }
        )

        facility2 = self._create_facility(partner_id=partner2.id)
        self.assertTrue(facility2.id)

    def test_partner_sync_on_update(self):
        """Partner update should sync to facility profile."""
        facility = self._create_facility()

        self.partner.write({"name": "Updated Facility Name"})

        facility.invalidate_recordset()
        self.assertEqual(facility.partner_id.name, "Updated Facility Name")
