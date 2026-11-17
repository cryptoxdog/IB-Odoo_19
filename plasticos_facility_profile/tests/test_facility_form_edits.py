"""Capability lines edit the site, and the full form opens from a line."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFacilityFormEdits(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Form Edit Parent", "is_company": True})
        cls.plant = cls.env["res.partner"].create(
            {"name": "Form Edit Plant", "is_company": True, "parent_id": parent.id}
        )
        cls.profile = cls.env["plasticos.facility.profile"].create({"partner_id": cls.plant.id})
        types = cls.env["plasticos.capability.type"]
        cls.shredding = types.search([("code", "=", "shredding")], limit=1)
        cls.pelletizing = types.search([("code", "=", "pelletizing")], limit=1)
        cls.baling = types.search([("code", "=", "baling")], limit=1)
        cls.assertTrue(cls.shredding, "capability type shredding is missing from seed data")
        cls.assertTrue(cls.pelletizing, "capability type pelletizing is missing from seed data")
        cls.assertTrue(cls.baling, "capability type baling is missing from seed data")

    def _line(self, cap_type, **vals):
        return self.env["plasticos.capability"].create(
            {"facility_profile_id": self.profile.id, "capability_type_id": cap_type.id, **vals}
        )

    def test_adding_shredding_keeps_pelletizing(self):
        pelletizing = self._line(self.pelletizing)
        shredding = self._line(self.shredding)
        self.assertEqual(set(self.profile.capability_ids), {pelletizing, shredding})
        shredding.unlink()
        self.assertEqual(self.profile.capability_ids, pelletizing)

    def test_baling_line_keeps_its_baler_detail(self):
        baling = self._line(self.baling, details={"baler": "hrb"})
        self.assertEqual(baling.capability_type_id, self.baling)
        self.assertEqual(baling.details["baler"], "hrb")

    def test_action_open_profile_form(self):
        action = self.profile.action_open_profile_form()
        self.assertEqual(action["res_model"], "plasticos.facility.profile")
        self.assertEqual(action["res_id"], self.profile.id)
        self.assertEqual(action["target"], "current")
