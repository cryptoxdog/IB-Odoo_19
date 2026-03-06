from odoo.addons.plasticos_base.tests.common import PlasticosTestCase
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestIntakeOnchange(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Intake = cls.env["plasticos.intake"]
        cls.partner = cls.env["res.partner"].create({"name": "One-Facility Co"})
        cls.facility = cls.env["res.partner"].create(
            {
                "name": "One Facility",
                "parent_id": cls.partner.id,
                "type": "delivery",
            }
        )

    def test_onchange_partner_autoselects_facility(self):
        intake = self.Intake.new({"partner_id": self.partner.id})
        intake._onchange_partner_id()
        self.assertEqual(intake.facility_id.id, self.facility.id)

    def test_onchange_facility_sets_contact(self):
        contact = self.env["res.partner"].create(
            {
                "name": "Preferred Contact",
                "parent_id": self.facility.id,
                "email": "c@example.com",
            }
        )
        intake = self.Intake.new({"facility_id": self.facility.id})
        intake._onchange_facility_id()
        self.assertIn(intake.contact_id, (False, contact))

    def test_onchange_material_attributes_flags_residue(self):
        intake = self.Intake.new({"contamination_pct": 5.0})
        intake._onchange_material_attributes()
        self.assertTrue(intake.has_residue)
