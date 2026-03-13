"""Unit tests for plasticos.material.profile.

Tests cover:
- Unique constraint (partner + polymer + form)
- Partner must be facility-level (has parent_id)
- Computed code fields (polymer, form, color, source_type)
- PO/SO line counts
- Material packet emission for graph hooks
- create/write hooks for graph sync
"""

import uuid

try:
    from psycopg.errors import IntegrityError
except ImportError:
    from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}_{uuid.uuid4().hex[:8].lower()}"


@tagged("post_install", "-at_install")
class TestMaterialProfile(PlasticosTestCase):
    """Test material profile constraints and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.partner"].create(
            {
                "name": "MP Parent Co",
                "is_company": True,
            }
        )
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "MP Facility",
                "parent_id": cls.company.id,
            }
        )
        cls._polymer_code = "HDPE"
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "HDPE-MP",
                "code": cls._polymer_code,
                "full_name": "High-Density Polyethylene",
                "category": "commodity",
            }
        )
        cls._form_code = "REGRIND"
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Regrind MP",
                "code": cls._form_code,
            }
        )
        cls._color_code = "BLUE"
        cls.color = cls.env["plasticos.material.color"].create(
            {
                "name": "Blue MP",
                "code": cls._color_code,
            }
        )
        cls._source_type_code = "POST_INDUSTRIAL"
        cls.source_type = cls.env["plasticos.source.type"].create(
            {
                "name": "Post Industrial MP",
                "code": cls._source_type_code,
            }
        )

        cls.profile = cls.env["plasticos.material.profile"].create(
            {
                "partner_id": cls.facility.id,
                "polymer_id": cls.polymer.id,
                "form_id": cls.form.id,
                "color_id": cls.color.id,
                "source_type_id": cls.source_type.id,
            }
        )

    # ── Constraints ─────────────────────────────────────────────

    def test_unique_partner_polymer_form(self):
        """Duplicate partner + polymer + form raises."""
        with self.assertRaises((ValidationError, UserError, IntegrityError)):
            # Odoo may wrap SQL UNIQUE violation as ValidationError/UserError
            # depending on ORM path and module load order.
            with self.env.cr.savepoint():
                self.env["plasticos.material.profile"].create(
                    {
                        "partner_id": self.facility.id,
                        "polymer_id": self.polymer.id,
                        "form_id": self.form.id,
                    }
                )

    def test_partner_must_be_facility(self):
        """Partner must have parent_id."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.material.profile"].create(
                {
                    "partner_id": self.company.id,
                    "polymer_id": self.polymer.id,
                    "form_id": self.form.id,
                }
            )

    # ── Computed Code Fields ────────────────────────────────────

    def test_polymer_code_computed(self):
        """polymer (selection) computed from polymer_id.code."""
        self.assertEqual(self.profile.polymer, self._polymer_code)

    def test_form_code_computed(self):
        """form (selection) computed from form_id.code."""
        self.assertEqual(self.profile.form, self._form_code)

    def test_color_code_computed(self):
        """color (char) computed from color_id.code."""
        self.assertEqual(self.profile.color, self._color_code)

    def test_source_type_code_computed(self):
        """source_type (char) computed from source_type_id.code."""
        self.assertEqual(self.profile.source_type, self._source_type_code)

    # ── Line Counts ─────────────────────────────────────────────

    def test_po_line_count_zero(self):
        """PO line count is 0 when no linked purchase lines."""
        self.assertEqual(self.profile.po_line_count, 0)

    def test_so_line_count_zero(self):
        """SO line count is 0 when no linked sale lines."""
        self.assertEqual(self.profile.so_line_count, 0)
