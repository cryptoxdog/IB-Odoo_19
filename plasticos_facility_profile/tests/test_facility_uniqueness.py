"""One capability profile per facility, checked across the whole operation."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFacilityUniqueness(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Facility Parent", "is_company": True})
        cls.plant_a = cls.env["res.partner"].create({"name": "Plant A", "is_company": True, "parent_id": parent.id})
        cls.plant_b = cls.env["res.partner"].create({"name": "Plant B", "is_company": True, "parent_id": parent.id})

    def test_same_batch_duplicate_partner_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["plasticos.facility.profile"].create(
                [{"partner_id": self.plant_a.id}, {"partner_id": self.plant_a.id}]
            )

    def test_multi_write_to_one_partner_is_rejected(self):
        first = self.env["plasticos.facility.profile"].create({"partner_id": self.plant_a.id})
        second = self.env["plasticos.facility.profile"].create({"partner_id": self.plant_b.id})
        with self.assertRaises(ValidationError):
            (first | second).write({"partner_id": self.plant_a.id})

    def test_distinct_partners_are_accepted(self):
        profiles = self.env["plasticos.facility.profile"].create(
            [{"partner_id": self.plant_a.id}, {"partner_id": self.plant_b.id}]
        )
        self.assertEqual(len(profiles), 2)

    def test_database_unique_partner_constraint_exists(self):
        self.env.cr.execute(
            """
            SELECT 1
              FROM pg_constraint
             WHERE conrelid = 'plasticos_facility_profile'::regclass
               AND contype = 'u'
               AND pg_get_constraintdef(oid) ILIKE '%%partner_id%%'
            """
        )
        self.assertTrue(self.env.cr.fetchone())
