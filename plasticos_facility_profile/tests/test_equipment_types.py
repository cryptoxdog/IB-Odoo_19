"""
Test equipment types.

Tests unique code constraint.
"""

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestEquipmentTypes(PlasticosTestCase):
    """Test plasticos.equipment.type model."""

    def test_create_equipment_type(self):
        """Equipment type can be created."""
        eq_type = self.env["plasticos.equipment.type"].create(
            {
                "name": "Extruder",
                "code": "EXT",
            }
        )
        self.assertTrue(eq_type.id)

    def test_unique_code_constraint(self):
        """Equipment type code must be unique."""
        self.env["plasticos.equipment.type"].create(
            {
                "name": "Extruder",
                "code": "EXT",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_equipment_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Extruder", "EXT"),
            )

    def test_different_codes_allowed(self):
        """Different codes should be allowed."""
        eq1 = self.env["plasticos.equipment.type"].create(
            {
                "name": "Extruder",
                "code": "EXT",
            }
        )
        eq2 = self.env["plasticos.equipment.type"].create(
            {
                "name": "Injection Molder",
                "code": "INJ",
            }
        )
        self.assertNotEqual(eq1.id, eq2.id)
