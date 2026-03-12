import uuid

from psycopg.errors import IntegrityError

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
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
        # Material profiles require a facility-level partner (one with a parent_id)
        parent_partner = cls.env["res.partner"].create({"name": "Parent Company A"})
        cls.partner = cls.env["res.partner"].create({"name": "Facility A", "parent_id": parent_partner.id})

        cls.polymer = cls.env["plasticos.polymer"].create({"name": "HDPE Test", "code": _unique_code("HDPE")})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Pellet Test", "code": _unique_code("PEL")})

    def _create_unique_form(self, prefix="FORM"):
        """Create a unique form for test isolation."""
        code = _unique_code(prefix)
        return self.env["plasticos.material.form"].create({"name": f"Form {code}", "code": code})

    # --- Registry unique constraints ----------------------------------------

    def test_polymer_code_unique(self):
        code = _unique_code("HDPE-UNIQ")
        self.env["plasticos.polymer"].create({"name": "HDPE-2", "code": code})
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.env["plasticos.polymer"].create({"name": "Duplicate", "code": code})

    def test_form_code_unique(self):
        code = _unique_code("FLAKE-UNIQ")
        self.env["plasticos.material.form"].create({"name": "Flake", "code": code})
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.env["plasticos.material.form"].create({"name": "Dup", "code": code})

    # --- Profile-level constraints -----------------------------------------

    def test_unique_profile_per_partner_polymer_form(self):
        # Use a unique form for this test to avoid conflicts with other tests
        unique_form = self._create_unique_form("UNIQ-PROF")
        self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": unique_form.id,
            }
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                self.Profile.create(
                    {
                        "partner_id": self.partner.id,
                        "polymer_id": self.polymer.id,
                        "form_id": unique_form.id,
                    }
                )

    def test_density_min_less_than_max(self):
        # Use a unique form for test isolation
        unique_form = self._create_unique_form("DENSITY")
        profile = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": unique_form.id,
                "density_min": 0.90,
                "density_max": 1.10,
            }
        )
        with self.assertRaises(ValidationError):
            profile.write({"density_min": 1.20, "density_max": 1.10})

    def test_mfi_min_less_than_max(self):
        # Use a unique form for test isolation
        unique_form = self._create_unique_form("MFI")
        profile = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": unique_form.id,
                "mfi_min": 1.0,
                "mfi_max": 10.0,
            }
        )
        with self.assertRaises(ValidationError):
            profile.write({"mfi_min": 20.0, "mfi_max": 5.0})
