import uuid

from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestMaterialProfileConstraints(PlasticosTestCase):
    """Covers SQL + python @api.constrains on material registry + profile."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility A"})

        cls.polymer = cls.env["plasticos.polymer"].create({"name": "HDPE Test", "code": _unique_code("HDPE")})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Pellet Test", "code": _unique_code("PEL")})

    # --- Registry unique constraints ----------------------------------------

    def test_polymer_code_unique(self):
        code = _unique_code("HDPE-UNIQ")
        self.env["plasticos.polymer"].create({"name": "HDPE-2", "code": code})
        raised = False
        try:
            self.env["plasticos.polymer"].create({"name": "Duplicate", "code": code})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_form_code_unique(self):
        code = _unique_code("FLAKE-UNIQ")
        self.env["plasticos.material.form"].create({"name": "Flake", "code": code})
        raised = False
        try:
            self.env["plasticos.material.form"].create({"name": "Dup", "code": code})
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    # --- Profile-level constraints -----------------------------------------

    def test_unique_profile_per_partner_polymer_form(self):
        self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
            }
        )
        raised = False
        try:
            self.Profile.create(
                {
                    "partner_id": self.partner.id,
                    "polymer_id": self.polymer.id,
                    "form_id": self.form.id,
                }
            )
        except (ValidationError, IntegrityError):
            raised = True
        self.assertTrue(raised, "Expected exception was not raised")

    def test_density_min_less_than_max(self):
        profile = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "density_min": 0.90,
                "density_max": 1.10,
            }
        )
        with self.assertRaises(ValidationError):
            profile.write({"density_min": 1.20, "density_max": 1.10})

    def test_mfi_min_less_than_max(self):
        profile = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "mfi_min": 1.0,
                "mfi_max": 10.0,
            }
        )
        with self.assertRaises(ValidationError):
            profile.write({"mfi_min": 20.0, "mfi_max": 5.0})
