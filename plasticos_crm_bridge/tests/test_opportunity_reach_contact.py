"""A location opportunity keeps the address and gains the linked person."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos", "crm_bridge")
class TestOpportunityReachContact(TransactionCase):
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
                "phone": "7045550100",
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
                "mobile": "9803225266",
            }
        )
        cls.doug.location_partner_ids = cls.location

    def _lead(self, **extra):
        vals = {
            "name": "Stanley — PP Buckets",
            "type": "opportunity",
            "partner_id": self.location.id,
        }
        vals.update(extra)
        return self.env["crm.lead"].create(vals)

    def test_location_opportunity_copies_the_person_and_keeps_the_address(self):
        lead = self._lead()
        self.assertEqual(lead.partner_id, self.location)
        self.assertEqual(lead.partner_name, "Sky Recycling")
        self.assertEqual(lead.street, "1250 Mac Lane")
        self.assertEqual(lead.contact_name, "Doug Noznesky")
        self.assertEqual(lead.email_from, "dnoz2004@bellsouth.net")
        self.assertEqual(lead.function, "Buyer")
        self.assertEqual(lead.phone, "7045550100")
        self.assertEqual(lead.mobile, "9803225266")
        self.assertFalse(self.location.email)

    def test_a_stored_contact_and_email_are_kept(self):
        lead = self._lead(contact_name="Pat", email_from="pat@example.test")
        self.assertEqual(lead.contact_name, "Pat")
        self.assertEqual(lead.email_from, "pat@example.test")

    def test_mirroring_the_person_does_not_write_the_location(self):
        bare = self.env["res.partner"].create(
            {"name": "Bare Stanley", "is_company": True, "parent_id": self.company.id, "street": "1 Mill Road"}
        )
        self.doug.location_partner_ids = bare
        lead = self.env["crm.lead"].create({"name": "Bare", "type": "opportunity", "partner_id": bare.id})
        self.assertEqual(lead.email_from, "dnoz2004@bellsouth.net")
        self.assertEqual(lead.phone, "9803225266")
        lead._inverse_email_from()
        lead._inverse_phone()
        self.assertFalse(bare.email)
        self.assertFalse(bare.phone)
        lead.email_from = "broker@example.test"
        self.assertEqual(bare.email, "broker@example.test")

    def test_a_short_mobile_is_not_copied(self):
        self.doug.mobile = "555"
        lead = self._lead()
        self.assertFalse(lead.mobile)

    def test_parent_contact_fills_a_location_with_nobody_linked(self):
        bare = self.env["res.partner"].create({"name": "Empty Site", "is_company": True, "parent_id": self.company.id})
        lead = self.env["crm.lead"].create({"name": "Empty", "type": "opportunity", "partner_id": bare.id})
        self.assertEqual(lead.contact_name, "Doug Noznesky")
        self.assertEqual(lead.email_from, "dnoz2004@bellsouth.net")

    def test_convert_sets_the_contact_and_keeps_the_location_partner(self):
        lead = self._lead()
        lead.action_convert_to_intake()
        intake = lead.source_intake_id
        self.assertEqual(intake.partner_id, self.location)
        self.assertEqual(intake.facility_id, self.location)
        self.assertEqual(intake.contact_id, self.doug)
        self.assertEqual(intake.contact_email, "dnoz2004@bellsouth.net")
