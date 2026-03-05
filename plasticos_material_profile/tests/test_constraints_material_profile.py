from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMaterialProfileConstraints(TransactionCase):
    """Covers SQL + python @api.constrains on material registry + profile."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility A"})

        cls.polymer = cls.env["plasticos.polymer"].create({"name": "HDPE", "code": "HDPE"})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Pellet", "code": "PEL"})

    # --- Registry unique constraints ----------------------------------------

    def test_polymer_code_unique(self):
        self.env["plasticos.polymer"].create({"name": "HDPE-2", "code": "HDPE-UNIQ"})
        with self.assertRaises((ValidationError, IntegrityError)):
            self.env["plasticos.polymer"].create({"name": "Duplicate", "code": "HDPE-UNIQ"})

    def test_form_code_unique(self):
        self.env["plasticos.material.form"].create({"name": "Flake", "code": "FLAKE-UNIQ"})
        with self.assertRaises((ValidationError, IntegrityError)):
            self.env["plasticos.material.form"].create({"name": "Dup", "code": "FLAKE-UNIQ"})

    # --- Profile-level constraints -----------------------------------------

    def test_unique_profile_per_partner_polymer_form(self):
        self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
            }
        )
        with self.assertRaises((ValidationError, IntegrityError)):
            self.Profile.create(
                {
                    "partner_id": self.partner.id,
                    "polymer_id": self.polymer.id,
                    "form_id": self.form.id,
                }
            )

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
