"""The normalizer packet carries the intake's polymer, form, and material grade codes."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "plasticos")
class TestPacketMaterialGrade(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.polymer = cls.env.ref("plasticos_material_profile.polymer_hdpe")
        cls.form_other = cls.env.ref("plasticos_material_profile.form_other")
        cls.form_sheet = cls.env.ref("plasticos_material_profile.form_sheet")
        cls.grade_drums = cls.env.ref("plasticos_material_profile.material_grade_drums")
        cls.partner = cls.env["res.partner"].create({"name": "Packet Grade Co", "is_company": True})

    def _intake(self, form, grade=None, **extra):
        vals = {
            "partner_id": self.partner.id,
            "polymer_id": self.polymer.id,
            "form_id": form.id,
            "material_grade_id": grade.id if grade else False,
            "quantity_per_load_lbs": 36000,
        }
        vals.update(extra)
        return self.env["plasticos.intake"].create(vals)

    def test_drums_packet_names_polymer_form_and_grade(self):
        packet = self._intake(self.form_other, self.grade_drums)._assemble_packet()

        self.assertEqual(packet["polymer"], "HDPE")
        self.assertEqual(packet["form"], "OTHER")
        self.assertEqual(packet["material_grade"], "DRUMS")

    def test_sheet_form_packet_has_no_grade(self):
        packet = self._intake(self.form_sheet)._assemble_packet()

        self.assertEqual(packet["form"], "SHEET")
        self.assertIsNone(packet["material_grade"])

    def test_profile_block_carries_the_profile_grade(self):
        profile = self.env["plasticos.material.profile"].create(
            {
                "partner_id": self.partner.id,
                "polymer_id": self.polymer.id,
                "material_grade_id": self.grade_drums.id,
                "form_id": self.form_other.id,
            }
        )
        intake = self._intake(self.form_other, self.grade_drums, material_profile_id=profile.id)

        block = intake._assemble_material_profile_block()

        self.assertEqual(block["material_grade"], "DRUMS")
        self.assertNotIn("grade", block)
