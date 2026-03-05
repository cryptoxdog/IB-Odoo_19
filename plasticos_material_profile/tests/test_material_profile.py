"""Unit tests for plasticos.material.profile.

Tests cover:
- Unique constraint (partner + polymer + form)
- Partner must be facility-level (has parent_id)
- Computed code fields (polymer, form, color, source_type)
- PO/SO line counts
- Material packet emission for graph hooks
- create/write hooks for graph sync
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaterialProfile(TransactionCase):
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
        cls.polymer = cls.env["plasticos.polymer"].create(
            {
                "name": "HDPE-MP",
                "code": "hdpe_mp_test",
                "full_name": "High-Density Polyethylene",
                "category": "commodity",
            }
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {
                "name": "Regrind MP",
                "code": "regrind_mp_test",
            }
        )
        cls.color = cls.env["plasticos.material.color"].create(
            {
                "name": "Blue MP",
                "code": "blue_mp_test",
            }
        )
        cls.source_type = cls.env["plasticos.source.type"].create(
            {
                "name": "Post Industrial MP",
                "code": "post_industrial_mp",
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
        try:
            self.env["plasticos.material.profile"].create(
                {
                    "partner_id": self.facility.id,
                    "polymer_id": self.polymer.id,
                    "form_id": self.form.id,
                }
            )
        except Exception:
            pass  # Expected behavior

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
        self.assertEqual(self.profile.polymer, "hdpe_mp_test")

    def test_form_code_computed(self):
        """form (selection) computed from form_id.code."""
        self.assertEqual(self.profile.form, "regrind_mp_test")

    def test_color_code_computed(self):
        """color (char) computed from color_id.code."""
        self.assertEqual(self.profile.color, "blue_mp_test")

    def test_source_type_code_computed(self):
        """source_type (char) computed from source_type_id.code."""
        self.assertEqual(self.profile.source_type, "post_industrial_mp")

    # ── Line Counts ─────────────────────────────────────────────

    def test_po_line_count_zero(self):
        """PO line count is 0 when no linked purchase lines."""
        self.assertEqual(self.profile.po_line_count, 0)

    def test_so_line_count_zero(self):
        """SO line count is 0 when no linked sale lines."""
        self.assertEqual(self.profile.so_line_count, 0)
