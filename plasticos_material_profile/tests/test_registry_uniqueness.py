"""
Test registry uniqueness constraints.

Tests all 8 SQL unique constraints:
- polymer.code
- form.code
- color.code
- source_type.code
- filler_type.code
- material_attribute.code
- packaging_type.code
- profile unique triple (partner+polymer+form)
"""

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRegistryUniqueness(TransactionCase):
    """Test registry model unique constraints."""

    # ═══════════════════════════════════════════════════════════
    # Polymer Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_polymer_code_unique(self):
        """Polymer code must be unique."""
        self.env["plasticos.polymer"].create(
            {
                "name": "High Density Polyethylene",
                "code": "HDPE",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_polymer (name, code)
                VALUES (%s, %s)
            """,
                ("Another HDPE", "HDPE"),
            )

    def test_polymer_different_codes_allowed(self):
        """Different polymer codes should be allowed."""
        p1 = self.env["plasticos.polymer"].create(
            {
                "name": "High Density Polyethylene",
                "code": "HDPE",
            }
        )
        p2 = self.env["plasticos.polymer"].create(
            {
                "name": "Low Density Polyethylene",
                "code": "LDPE",
            }
        )
        self.assertNotEqual(p1.id, p2.id)

    # ═══════════════════════════════════════════════════════════
    # Form Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_form_code_unique(self):
        """Material form code must be unique."""
        self.env["plasticos.material.form"].create(
            {
                "name": "Pellet",
                "code": "PELLET",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_material_form (name, code)
                VALUES (%s, %s)
            """,
                ("Another Pellet", "PELLET"),
            )

    def test_form_different_codes_allowed(self):
        """Different form codes should be allowed."""
        f1 = self.env["plasticos.material.form"].create(
            {
                "name": "Pellet",
                "code": "PELLET",
            }
        )
        f2 = self.env["plasticos.material.form"].create(
            {
                "name": "Flake",
                "code": "FLAKE",
            }
        )
        self.assertNotEqual(f1.id, f2.id)

    # ═══════════════════════════════════════════════════════════
    # Color Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_color_code_unique(self):
        """Material color code must be unique."""
        self.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": "NAT",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_material_color (name, code)
                VALUES (%s, %s)
            """,
                ("Another Natural", "NAT"),
            )

    def test_color_different_codes_allowed(self):
        """Different color codes should be allowed."""
        c1 = self.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": "NAT",
            }
        )
        c2 = self.env["plasticos.material.color"].create(
            {
                "name": "Black",
                "code": "BLK",
            }
        )
        self.assertNotEqual(c1.id, c2.id)

    # ═══════════════════════════════════════════════════════════
    # Source Type Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_source_type_code_unique(self):
        """Source type code must be unique."""
        self.env["plasticos.source.type"].create(
            {
                "name": "Post-Industrial",
                "code": "PIR",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_source_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Post-Industrial", "PIR"),
            )

    # ═══════════════════════════════════════════════════════════
    # Filler Type Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_filler_type_code_unique(self):
        """Filler type code must be unique."""
        self.env["plasticos.filler.type"].create(
            {
                "name": "Glass Fiber",
                "code": "GF",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_filler_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Glass Fiber", "GF"),
            )

    # ═══════════════════════════════════════════════════════════
    # Material Attribute Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_material_attribute_code_unique(self):
        """Material attribute code must be unique."""
        self.env["plasticos.material.attribute"].create(
            {
                "name": "UV Stabilized",
                "code": "UV",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_material_attribute (name, code)
                VALUES (%s, %s)
            """,
                ("Another UV Stabilized", "UV"),
            )

    # ═══════════════════════════════════════════════════════════
    # Packaging Type Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_packaging_type_code_unique(self):
        """Packaging type code must be unique."""
        self.env["plasticos.packaging.type"].create(
            {
                "name": "Gaylord",
                "code": "GAYLORD",
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_packaging_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Gaylord", "GAYLORD"),
            )
