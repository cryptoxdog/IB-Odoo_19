from psycopg2 import IntegrityError

from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestMaterialProfileConstraintsConsolidated(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        cls.partner = cls.env["res.partner"].create({"name": "Facility"})

        cls.polymer = cls.env["plasticos.polymer"].search([("code", "=", "HDPE")], limit=1)
        if not cls.polymer:
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
