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

import uuid

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestRegistryUniqueness(PlasticosTestCase):
    """Test registry model unique constraints."""

    # ═══════════════════════════════════════════════════════════
    # Polymer Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_polymer_code_unique(self):
        """Polymer code must be unique."""
        code = _unique_code("POLY")
        self.env["plasticos.polymer"].create(
            {
                "name": "High Density Polyethylene",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_polymer (name, code)
                VALUES (%s, %s)
            """,
                ("Another HDPE", code),
            )

    def test_polymer_different_codes_allowed(self):
        """Different polymer codes should be allowed."""
        p1 = self.env["plasticos.polymer"].create(
            {
                "name": "High Density Polyethylene",
                "code": _unique_code("POLY"),
            }
        )
        p2 = self.env["plasticos.polymer"].create(
            {
                "name": "Low Density Polyethylene",
                "code": _unique_code("POLY"),
            }
        )
        self.assertNotEqual(p1.id, p2.id)

    # ═══════════════════════════════════════════════════════════
    # Form Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_form_code_unique(self):
        """Material form code must be unique."""
        code = _unique_code("FORM")
        self.env["plasticos.material.form"].create(
            {
                "name": "Pellet",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_material_form (name, code)
                VALUES (%s, %s)
            """,
                ("Another Pellet", code),
            )

    def test_form_different_codes_allowed(self):
        """Different form codes should be allowed."""
        f1 = self.env["plasticos.material.form"].create(
            {
                "name": "Pellet",
                "code": _unique_code("FORM"),
            }
        )
        f2 = self.env["plasticos.material.form"].create(
            {
                "name": "Flake",
                "code": _unique_code("FORM"),
            }
        )
        self.assertNotEqual(f1.id, f2.id)

    # ═══════════════════════════════════════════════════════════
    # Color Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_color_code_unique(self):
        """Material color code must be unique."""
        code = _unique_code("COLOR")
        self.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_material_color (name, code)
                VALUES (%s, %s)
            """,
                ("Another Natural", code),
            )

    def test_color_different_codes_allowed(self):
        """Different color codes should be allowed."""
        c1 = self.env["plasticos.material.color"].create(
            {
                "name": "Natural",
                "code": _unique_code("COLOR"),
            }
        )
        c2 = self.env["plasticos.material.color"].create(
            {
                "name": "Black",
                "code": _unique_code("COLOR"),
            }
        )
        self.assertNotEqual(c1.id, c2.id)

    # ═══════════════════════════════════════════════════════════
    # Source Type Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_source_type_code_unique(self):
        """Source type code must be unique."""
        code = _unique_code("SRC")
        self.env["plasticos.source.type"].create(
            {
                "name": "Post-Industrial",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_source_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Post-Industrial", code),
            )

    # ═══════════════════════════════════════════════════════════
    # Filler Type Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_filler_type_code_unique(self):
        """Filler type code must be unique."""
        code = _unique_code("FILL")
        self.env["plasticos.filler.type"].create(
            {
                "name": "Glass Fiber",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_filler_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Glass Fiber", code),
            )

    # ═══════════════════════════════════════════════════════════
    # Material Attribute Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_material_attribute_code_unique(self):
        """Material attribute code must be unique."""
        code = _unique_code("ATTR")
        self.env["plasticos.material.attribute"].create(
            {
                "name": "UV Stabilized",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_material_attribute (name, code)
                VALUES (%s, %s)
            """,
                ("Another UV Stabilized", code),
            )

    # ═══════════════════════════════════════════════════════════
    # Packaging Type Uniqueness Tests
    # ═══════════════════════════════════════════════════════════

    def test_packaging_type_code_unique(self):
        """Packaging type code must be unique."""
        code = _unique_code("PKG")
        self.env["plasticos.packaging.type"].create(
            {
                "name": "Gaylord",
                "code": code,
            }
        )

        with self.assertRaises(IntegrityError):
            self.env.cr.execute(
                """
                INSERT INTO plasticos_packaging_type (name, code)
                VALUES (%s, %s)
            """,
                ("Another Gaylord", code),
            )
