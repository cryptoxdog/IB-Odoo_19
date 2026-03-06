"""Tests for plasticos.material.profile — constraints, computed fields, navigation.

Target module: plasticos_material_profile
Target model:  plasticos.material.profile
"""

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaterialProfileEnhanced(TransactionCase):
    """Test material profile creation, constraints, and computed fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.Polymer = cls.env["plasticos.polymer"]
        cls.Form = cls.env["plasticos.material.form"]
        cls.Color = cls.env["plasticos.material.color"]
        cls.SourceType = cls.env["plasticos.source.type"]

        # Master data
        cls.company = cls.env["res.partner"].create({"name": "Acme Plastics"})
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "Acme Atlanta Facility",
                "parent_id": cls.company.id,
            }
        )
        cls.polymer_pp = cls.Polymer.create({"name": "Polypropylene", "code": "PP_ENH"})
        cls.polymer_hdpe = cls.Polymer.create({"name": "HDPE", "code": "HDPE_ENH"})
        cls.form_regrind = cls.Form.create({"name": "Regrind", "code": "REGRIND_ENH"})
        cls.form_pellet = cls.Form.create({"name": "Pellet", "code": "PELLET_ENH"})
        cls.color_natural = cls.Color.create({"name": "Natural", "code": "NATURAL_ENH"})
        cls.source_pi = cls.SourceType.create(
            {
                "name": "Post-Industrial",
                "code": "POST_INDUSTRIAL_ENH",
            }
        )

    # ── Basic creation ───────────────────────────────────────

    def test_create_material_profile(self):
        """Create a valid material profile."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        self.assertTrue(profile.id)
        self.assertEqual(profile.company_id.id, self.company.id)

    # ── Computed backward-compat fields ──────────────────────

    def test_polymer_code_computed(self):
        """polymer selection field auto-computes from polymer_id.code."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        self.assertEqual(profile.polymer, "PP_ENH")

    def test_color_code_computed(self):
        """color selection field auto-computes from color_id.code."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
                "color_id": self.color_natural.id,
            }
        )
        self.assertEqual(profile.color, "NATURAL_ENH")

    def test_source_type_code_computed(self):
        """source_type selection auto-computes from source_type_id.code."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
                "source_type_id": self.source_pi.id,
            }
        )
        self.assertEqual(profile.source_type, "POST_INDUSTRIAL_ENH")

    # ── Constraints ──────────────────────────────────────────

    def test_partner_must_be_facility(self):
        """Profile cannot attach to a top-level partner (no parent_id)."""
        with self.assertRaises(ValidationError):
            self.Profile.create(
                {
                    "partner_id": self.company.id,
                    "polymer_id": self.polymer_pp.id,
                    "form_id": self.form_regrind.id,
                }
            )

    def test_unique_partner_polymer_form(self):
        """Duplicate polymer + form per facility is blocked."""
        self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            self.Profile.create(
                {
                    "partner_id": self.facility.id,
                    "polymer_id": self.polymer_pp.id,
                    "form_id": self.form_regrind.id,
                }
            )

    def test_different_polymer_same_form_allowed(self):
        """Same facility + same form but different polymer is allowed."""
        self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        profile2 = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_hdpe.id,
                "form_id": self.form_regrind.id,
            }
        )
        self.assertTrue(profile2.id)

    # ── Navigation Actions ───────────────────────────────────

    def test_action_view_facility(self):
        """action_view_facility returns action window for partner."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        result = profile.action_view_facility()
        self.assertEqual(result["res_model"], "res.partner")
        self.assertEqual(result["res_id"], self.facility.id)

    def test_action_view_company(self):
        """action_view_company returns action window for parent company."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        result = profile.action_view_company()
        self.assertEqual(result["res_model"], "res.partner")
        self.assertEqual(result["res_id"], self.company.id)

    def test_action_open_profile_form(self):
        """action_open_profile_form returns correct action."""
        profile = self.Profile.create(
            {
                "partner_id": self.facility.id,
                "polymer_id": self.polymer_pp.id,
                "form_id": self.form_regrind.id,
            }
        )
        result = profile.action_open_profile_form()
        self.assertEqual(result["res_model"], "plasticos.material.profile")
        self.assertEqual(result["res_id"], profile.id)
