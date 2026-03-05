from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMaterialProfileConstraintsConsolidated(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility"})

        cls.polymer = cls.env["plasticos.polymer"].create({"name": "HDPE", "code": "HDPE"})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Pellet", "code": "PEL"})

    def test_unique_polymer_form_partner(self):
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

    def test_density_bounds(self):
        prof = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
                "density_min": 0.9,
                "density_max": 1.1,
            }
        )
        with self.assertRaises(ValidationError):
            prof.write({"density_min": 1.2, "density_max": 1.1})
