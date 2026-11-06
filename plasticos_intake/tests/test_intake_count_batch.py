"""Intake counts on partners and material profiles are grouped queries, each intake counted once."""

from odoo.addons.plasticos_base.test_common import PlasticosTestCase
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "intake")
class TestIntakeCountBatch(PlasticosTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.partner"].create({"name": "Intake Count HQ", "is_company": True})
        cls.facility = cls.env["res.partner"].create(
            {"name": "Intake Count Plant", "is_company": True, "parent_id": cls.company.id}
        )
        cls.unrelated = cls.env["res.partner"].create({"name": "Intake Count Bystander", "is_company": True})

    def _partner_cost(self, partners):
        partners.invalidate_recordset(["intake_count"])
        before = self.env.cr.sql_log_count
        partners.mapped("intake_count")
        return self.env.cr.sql_log_count - before

    def test_partner_intake_count_counts_supplier_or_facility_once_per_intake(self):
        # company as supplier with the plant as facility: one for each
        self._create_intake(partner=self.company, facility_id=self.facility.id)
        # plant as both supplier and facility: one for the plant, not two
        self._create_intake(partner=self.facility, facility_id=self.facility.id)
        # company as supplier with no facility
        self._create_intake(partner=self.company)
        trio = self.company | self.facility | self.unrelated
        trio.invalidate_recordset(["intake_count"])
        self.assertEqual(trio.mapped("intake_count"), [2, 2, 0])
        fresh = self.env["res.partner"].new({})
        self.assertEqual((fresh | trio).mapped("intake_count"), [0, 2, 2, 0])
        one_cost = self._partner_cost(self.company)
        three_cost = self._partner_cost(trio)
        self.assertGreaterEqual(one_cost, 1)
        self.assertLess(three_cost, one_cost * 2)

    def test_profile_intake_count_is_grouped_across_profiles(self):
        polymer = self._get_or_create_polymer()
        form = self._get_or_create_form()
        other_polymer = self._get_or_create_polymer(code="PP")
        profile_model = self.env["plasticos.material.profile"]
        first = profile_model.create({"partner_id": self.facility.id, "polymer_id": polymer.id, "form_id": form.id})
        second = profile_model.create(
            {"partner_id": self.facility.id, "polymer_id": other_polymer.id, "form_id": form.id}
        )
        self._create_intake(partner=self.company, polymer=polymer, form=form, material_profile_id=first.id)
        pair = first | second
        pair.invalidate_recordset(["intake_count"])
        self.assertEqual(pair.mapped("intake_count"), [1, 0])
        fresh = profile_model.new({})
        self.assertEqual((fresh | pair).mapped("intake_count"), [0, 1, 0])
        pair.invalidate_recordset(["intake_count"])
        before = self.env.cr.sql_log_count
        pair.mapped("intake_count")
        two_cost = self.env.cr.sql_log_count - before
        first.invalidate_recordset(["intake_count"])
        before = self.env.cr.sql_log_count
        first.mapped("intake_count")
        one_cost = self.env.cr.sql_log_count - before
        self.assertGreaterEqual(one_cost, 1)
        self.assertLess(two_cost, one_cost * 2)
