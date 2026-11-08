"""CRM-4 profile reuse stays unwired from live sync."""

import uuid

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCrm4ProfileReuse(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.profile = cls.env["plasticos.material.profile"]
        parent = cls.env["res.partner"].create({"name": "CRM4 Parent", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {"name": "CRM4 Facility", "is_company": True, "parent_id": parent.id}
        )
        cls.polymer = cls.env["plasticos.polymer"].create(
            {"name": "CRM4 Polymer", "code": f"CRM4-{uuid.uuid4().hex[:8].upper()}"}
        )
        cls.form = cls.env["plasticos.material.form"].create(
            {"name": "CRM4 Bale", "code": f"CRM4B-{uuid.uuid4().hex[:8].upper()}"}
        )
        cls.other_form = cls.env["plasticos.material.form"].create(
            {"name": "CRM4 Regrind", "code": f"CRM4R-{uuid.uuid4().hex[:8].upper()}"}
        )
        cls.user = cls.env["res.users"].create({"name": "CRM4 Salesperson", "login": f"crm4-{uuid.uuid4().hex[:8]}"})
        cls.lead = cls.env["crm.lead"].create({"name": "CRM4 Lead", "user_id": cls.user.id})

    def _domain(self, form_id=None):
        domain = [("partner_id", "=", self.partner.id), ("polymer_id", "=", self.polymer.id)]
        if form_id is not None:
            domain.append(("form_id", "=", form_id))
        return domain

    def test_one_form_is_stored(self):
        profile = self.profile.reuse_facility_polymer_profile(self.partner, self.polymer, self.form)
        self.assertEqual(profile.form_id, self.form)
        self.assertEqual(self.profile.search_count(self._domain(self.form.id)), 1)

    def test_zero_or_many_forms_collapse_to_one_empty_form_profile(self):
        none = self.env["plasticos.material.form"]
        many = self.form | self.other_form
        first = self.profile.reuse_facility_polymer_profile(self.partner, self.polymer, none)
        second = self.profile.reuse_facility_polymer_profile(self.partner, self.polymer, many)
        self.assertFalse(first.form_id)
        self.assertEqual(first, second)
        self.assertEqual(self.profile.search_count(self._domain()), 1)
        self.assertFalse(self.profile.search(self._domain() + [("form_id", "!=", False)]))

    def test_note_appends_once_and_replay_returns_the_same_profile(self):
        note = "Plant manager confirmed the polymer."
        first = self.profile.reuse_facility_polymer_profile(self.partner, self.polymer, self.form, note_line=note)
        second = self.profile.reuse_facility_polymer_profile(self.partner, self.polymer, self.form, note_line=note)
        self.assertEqual(second.id, first.id)
        self.assertEqual((first.freeform_notes or "").splitlines().count(note), 1)
        self.assertEqual(self.profile.search_count(self._domain()), 1)

    def test_lead_salesperson_is_untouched(self):
        self.profile.reuse_facility_polymer_profile(self.partner, self.polymer, self.form)
        self.assertEqual(self.lead.user_id, self.user)
