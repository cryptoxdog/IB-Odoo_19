"""The person a location can be reached through."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "facility")
class TestReachPerson(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"]
        cls.company = partner.create({"name": "Sky Recycling", "is_company": True})
        cls.location = partner.create(
            {
                "name": "Stanley",
                "is_company": True,
                "parent_id": cls.company.id,
                "street": "1250 Mac Lane",
            }
        )
        cls.doug = partner.create(
            {
                "name": "Doug Noznesky",
                "is_company": False,
                "type": "contact",
                "parent_id": cls.company.id,
                "email": "dnoz2004@bellsouth.net",
                "phone": "9803225266",
                "function": "Buyer",
            }
        )
        cls.doug.location_partner_ids = cls.location

    def test_linked_person_with_email_is_the_header_person(self):
        self.assertEqual(self.location._plasticos_reach_person(), self.doug)
        self.assertEqual(self.location.linked_person_email, "dnoz2004@bellsouth.net")

    def test_linked_person_without_email_does_not_fall_through(self):
        quiet = self.env["res.partner"].create(
            {
                "name": "Quiet Contact",
                "is_company": False,
                "type": "contact",
                "parent_id": self.company.id,
            }
        )
        self.doug.location_partner_ids = self.env["res.partner"]
        quiet.location_partner_ids = self.location
        self.assertEqual(self.location._plasticos_reach_person(), quiet)

    def test_no_linked_person_uses_the_parent_contact(self):
        self.doug.location_partner_ids = self.env["res.partner"]
        self.assertEqual(self.location._plasticos_reach_person(), self.doug)

    def test_several_location_children_are_not_guessed(self):
        self.doug.location_partner_ids = self.env["res.partner"]
        self.env["res.partner"].create(
            {"name": "Child One", "is_company": False, "type": "contact", "parent_id": self.location.id}
        )
        self.env["res.partner"].create(
            {"name": "Child Two", "is_company": False, "type": "contact", "parent_id": self.location.id}
        )
        self.assertFalse(self.location._plasticos_reach_person())

    def test_one_location_child_is_used_when_nobody_is_linked(self):
        self.doug.location_partner_ids = self.env["res.partner"]
        child = self.env["res.partner"].create(
            {
                "name": "Only Child",
                "is_company": False,
                "type": "contact",
                "parent_id": self.location.id,
                "email": "only@example.test",
            }
        )
        self.assertEqual(self.location._plasticos_reach_person(), child)

    def test_a_person_resolves_to_itself(self):
        self.assertEqual(self.doug._plasticos_reach_person(), self.doug)

    def test_a_company_with_several_children_is_not_guessed(self):
        self.env["res.partner"].create(
            {"name": "Second Person", "is_company": False, "type": "contact", "parent_id": self.company.id}
        )
        self.assertFalse(self.company._plasticos_reach_person())

    def test_preferred_wins_only_inside_the_linked_set(self):
        other = self.env["res.partner"].create(
            {
                "name": "Other Person",
                "is_company": False,
                "type": "contact",
                "parent_id": self.company.id,
                "email": "other@example.test",
            }
        )
        self.location.preferred_contact_id = other
        self.assertEqual(self.location._plasticos_reach_person(), self.doug)
        other.location_partner_ids = self.location
        self.location.preferred_contact_id = other
        self.assertEqual(self.location._plasticos_reach_person(), other)
