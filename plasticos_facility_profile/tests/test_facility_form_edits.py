"""Equipment toggles edit the equipment list, and the full form opens from a line."""

from odoo import Command
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
        equipment = cls.env["plasticos.equipment.type"]
        cls.shredder = equipment.search([("code", "=", "shredder")], limit=1)
        cls.pelletizer = equipment.search([("code", "=", "pelletizer")], limit=1)
        cls.horizontal_baler = equipment.search([("code", "=", "horizontal_baler")], limit=1)
        cls.assertTrue(cls.shredder, "equipment type shredder is missing from seed data")
        cls.assertTrue(cls.pelletizer, "equipment type pelletizer is missing from seed data")
        cls.assertTrue(cls.horizontal_baler, "equipment type horizontal_baler is missing from seed data")

    def test_shredder_toggle_keeps_unrelated_equipment(self):
        self.profile.write({"equipment_type_ids": [Command.link(self.pelletizer.id)]})
        self.profile.has_shredder = True
        self.assertIn(self.shredder, self.profile.equipment_type_ids)
        self.assertIn(self.pelletizer, self.profile.equipment_type_ids)
        self.profile.has_shredder = False
        self.assertNotIn(self.shredder, self.profile.equipment_type_ids)
        self.assertIn(self.pelletizer, self.profile.equipment_type_ids)

    def test_equipment_type_still_sets_horizontal_baler_flag(self):
        self.profile.write({"equipment_type_ids": [Command.link(self.horizontal_baler.id)]})
        self.assertTrue(self.profile.has_horizontal_baler)

    def test_action_open_profile_form(self):
        action = self.profile.action_open_profile_form()
        self.assertEqual(action["res_model"], "plasticos.facility.profile")
        self.assertEqual(action["res_id"], self.profile.id)
        self.assertEqual(action["target"], "current")
