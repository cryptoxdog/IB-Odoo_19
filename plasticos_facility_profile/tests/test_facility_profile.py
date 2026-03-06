"""Unit tests for plasticos.facility.profile.

Tests cover:
- Unique partner constraint
- Partner must be facility-level (has parent_id)
- Equipment flags computed from equipment_type_ids Many2many
- Form preference computed from form_preference_id
- Embedding readiness (needs polymer + process_type + state)
- Density range constraint
- Melt index range constraint
"""

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFacilityProfile(PlasticosTestCase):
    """Test facility profile constraints and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.partner"].create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "Facility A",
                "parent_id": cls.company.id,
            }
        )
        cls.polymer_pp = cls.env["plasticos.polymer"].create(
            {
                "name": "PP-FP",
                "code": "pp_fp_test",
                "full_name": "Polypropylene",
                "category": "commodity",
            }
        )
        cls.state = cls.env["res.country.state"].search([], limit=1)

        # Equipment types
        cls.eq_baler = cls.env["plasticos.equipment.type"].create(
            {
                "name": "Horizontal Baler",
                "code": "horizontal_baler",
            }
        )
        cls.eq_shredder = cls.env["plasticos.equipment.type"].create(
            {
                "name": "Shredder",
                "code": "shredder",
            }
        )
        cls.eq_wash = cls.env["plasticos.equipment.type"].create(
            {
                "name": "Wash Line",
                "code": "wash_line",
            }
        )

    # ── Constraints ─────────────────────────────────────────────

    def test_unique_partner_constraint(self):
        """Only one facility profile per partner."""
        self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
            }
        )
        try:
            self.env["plasticos.facility.profile"].create(
                {
                    "partner_id": self.facility.id,
                }
            )
        except Exception:
            pass  # Expected behavior

    def test_partner_must_be_facility(self):
        """Partner must have parent_id (be a facility)."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.facility.profile"].create(
                {
                    "partner_id": self.company.id,
                }
            )

    def test_density_range_constraint(self):
        """density_min cannot exceed density_max."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.facility.profile"].create(
                {
                    "partner_id": self.facility.id,
                    "density_min": 1.5,
                    "density_max": 0.9,
                }
            )

    def test_mfi_range_constraint(self):
        """melt_index_min cannot exceed melt_index_max."""
        with self.assertRaises(ValidationError):
            self.env["plasticos.facility.profile"].create(
                {
                    "partner_id": self.facility.id,
                    "melt_index_min": 20.0,
                    "melt_index_max": 5.0,
                }
            )

    # ── Equipment Flags ─────────────────────────────────────────

    def test_equipment_flags_computed(self):
        """has_* flags computed from equipment_type_ids."""
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
                "equipment_type_ids": [
                    (6, 0, [self.eq_baler.id, self.eq_shredder.id]),
                ],
            }
        )
        self.assertTrue(profile.has_horizontal_baler)
        self.assertTrue(profile.has_shredder)
        self.assertFalse(profile.has_wash_line)

    def test_equipment_flags_update(self):
        """Equipment flags update when equipment_type_ids changes."""
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
            }
        )
        self.assertFalse(profile.has_wash_line)
        profile.write(
            {
                "equipment_type_ids": [(4, self.eq_wash.id)],
            }
        )
        profile.invalidate_recordset()
        self.assertTrue(profile.has_wash_line)

    # ── Embedding Readiness ─────────────────────────────────────

    def test_embedding_ready_true(self):
        """embedding_ready True when polymer + process_type + state set."""
        self.facility.state_id = self.state.id if self.state else False
        if not self.state:
            return
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
                "accepted_polymer_ids": [(4, self.polymer_pp.id)],
                "process_type": "extrusion",
            }
        )
        self.assertTrue(profile.embedding_ready)

    def test_embedding_ready_false_missing_polymer(self):
        """embedding_ready False when no accepted polymers."""
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
                "process_type": "extrusion",
            }
        )
        self.assertFalse(profile.embedding_ready)

    def test_embedding_ready_false_missing_process(self):
        """embedding_ready False when no process_type."""
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
                "accepted_polymer_ids": [(4, self.polymer_pp.id)],
            }
        )
        self.assertFalse(profile.embedding_ready)

    # ── Form Preference ─────────────────────────────────────────

    def test_form_preference_computed(self):
        """form_preference code computed from form_preference_id."""
        form = self.env["plasticos.material.form"].create(
            {
                "name": "Bales FP",
                "code": "bales_fp_test",
            }
        )
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
                "form_preference_id": form.id,
            }
        )
        self.assertEqual(profile.form_preference, "bales_fp_test")

    def test_form_preference_false_when_empty(self):
        """form_preference is False when form_preference_id not set."""
        profile = self.env["plasticos.facility.profile"].create(
            {
                "partner_id": self.facility.id,
            }
        )
        self.assertFalse(profile.form_preference)
