"""Intake create and the facility form take the location's reached person."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests import Form, tagged


@tagged("post_install", "-at_install", "plasticos", "intake")
class TestIntakeReachContact(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"]
        cls.company = partner.create({"name": "Sky Recycling", "is_company": True})
        cls.location = partner.create(
            {"name": "Stanley", "is_company": True, "parent_id": cls.company.id, "street": "1250 Mac Lane"}
        )
        cls.doug = partner.create(
            {
                "name": "Doug Noznesky",
                "is_company": False,
                "type": "contact",
                "parent_id": cls.company.id,
                "email": "dnoz2004@bellsouth.net",
            }
        )
        cls.doug.location_partner_ids = cls.location
        cls.polymer = cls._get_or_create_polymer()
        cls.form_type = cls._get_or_create_form()

    def test_create_sets_the_linked_person_and_email(self):
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.location.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form_type.id,
            }
        )
        self.assertEqual(intake.contact_id, self.doug)
        self.assertEqual(intake.contact_email, "dnoz2004@bellsouth.net")
        self.assertEqual(intake.partner_id, self.location)

    def test_form_onchange_sets_the_linked_person(self):
        form = Form(self.env["plasticos.intake"])
        form.partner_id = self.company
        form.facility_id = self.location
        self.assertEqual(form.contact_id, self.doug)

    def test_an_explicit_contact_is_kept(self):
        other = self.env["res.partner"].create(
            {"name": "Kept Person", "is_company": False, "type": "contact", "parent_id": self.company.id}
        )
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.location.id,
                "contact_id": other.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form_type.id,
            }
        )
        self.assertEqual(intake.contact_id, other)

    def test_parent_contact_is_used_when_the_location_has_nobody_linked(self):
        self.doug.location_partner_ids = self.env["res.partner"]
        intake = self.env["plasticos.intake"].create(
            {
                "partner_id": self.location.id,
                "facility_id": self.location.id,
                "polymer_id": self.polymer.id,
                "form_id": self.form_type.id,
            }
        )
        self.assertEqual(intake.contact_id, self.doug)
        self.assertEqual(intake.contact_email, "dnoz2004@bellsouth.net")
