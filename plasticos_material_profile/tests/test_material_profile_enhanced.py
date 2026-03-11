"""Tests for plasticos.material.profile — constraints, computed fields, navigation.

Target module: plasticos_material_profile
Target model:  plasticos.material.profile
"""

import uuid

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestMaterialProfileEnhanced(PlasticosTestCase):
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
        cls._pp_code = _unique_code("PP_ENH")
        cls.polymer_pp = cls.Polymer.create({"name": "Polypropylene", "code": cls._pp_code})
        cls.polymer_hdpe = cls.Polymer.create({"name": "HDPE", "code": _unique_code("HDPE_ENH")})
        cls.form_regrind = cls.Form.create({"name": "Regrind", "code": _unique_code("REGRIND_ENH")})
        cls.form_pellet = cls.Form.create({"name": "Pellet", "code": _unique_code("PELLET_ENH")})
        cls._natural_code = _unique_code("NATURAL_ENH")
        cls.color_natural = cls.Color.create({"name": "Natural", "code": cls._natural_code})
        cls._pi_code = _unique_code("POST_INDUSTRIAL_ENH")
        cls.source_pi = cls.SourceType.create(
            {
                "name": "Post-Industrial",
                "code": cls._pi_code,
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
        self.assertEqual(profile.polymer, self._pp_code)

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
        self.assertEqual(profile.color, self._natural_code)

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
        self.assertEqual(profile.source_type, self._pi_code)

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
