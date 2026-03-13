import uuid

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.exceptions import ValidationError
from odoo.tests import tagged


def _unique_code(prefix="TEST"):
    """Generate a unique code for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


@tagged("post_install", "-at_install")
class TestMaterialProfileConstraintsConsolidated(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env["plasticos.material.profile"]
        # Partner must have parent_id to satisfy _check_partner_is_facility constraint
        cls.parent_company = cls.env["res.partner"].create({"name": "Parent Co", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Facility",
                "parent_id": cls.parent_company.id,
            }
        )

        cls.polymer = cls.env["plasticos.polymer"].create({"name": "HDPE", "code": _unique_code("HDPE")})
        cls.form = cls.env["plasticos.material.form"].create({"name": "Pellet", "code": _unique_code("PEL")})

    def test_unique_polymer_form_partner(self):
        self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form.id,
            }
        )
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.Profile.create(
                    {
                        "partner_id": self.partner.id,
                        "polymer_id": self.polymer.id,
                        "form_id": self.form.id,
                    }
                )

    def test_density_bounds(self):
        unique_form = self.env["plasticos.material.form"].create({"name": "Density Form", "code": _unique_code("DENS")})
        prof = self.Profile.create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "form_id": unique_form.id,
                "density_min": 0.9,
                "density_max": 1.1,
            }
        )
        with self.assertRaises(ValidationError):
            prof.write({"density_min": 1.2, "density_max": 1.1})
