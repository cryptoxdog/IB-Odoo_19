"""Approved material phrases resolve to existing masters and nothing else."""

from odoo.addons.plasticos_material_profile.models.material_normalizer import normalize_material
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMaterialNormalizer(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        parent = cls.env["res.partner"].create({"name": "Normalizer Parent", "is_company": True})
        cls.partner = cls.env["res.partner"].create(
            {"name": "Normalizer Facility", "parent_id": parent.id, "is_company": True}
        )

    def test_approved_phrases_resolve_and_unknown_fabricates_nothing(self):
        cases = {
            "99 Clear LDPE Film": ("LDPE", "FILM", False, {"clean", "dry"}, "A"),
            "LDPE Grade A Film": ("LDPE", "FILM", False, {"clean", "dry"}, "A"),
            "95 Clear LDPE Film": ("LDPE", "FILM", False, {"clean"}, "B"),
            "LDPE Grade B Film": ("LDPE", "FILM", False, {"clean"}, "B"),
            "90 Clear LDPE Film": ("LDPE", "FILM", False, set(), "C"),
            "LDPE Grade C Film": ("LDPE", "FILM", False, set(), "C"),
            "PP Film (BOPP)": ("BOPP", "FILM", False, set(), None),
            "PC/ABS": ("PC_ABS", False, "POST_INDUSTRIAL", set(), None),
            "PC-ABS": ("PC_ABS", False, "POST_INDUSTRIAL", set(), None),
            "3-7": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", set(), None),
            "3-7 Commingled Bottles": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", set(), None),
            "1-7": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", set(), None),
            "1-7 Commingled Bottles": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", "POST_CONSUMER", set(), None),
            "PE": ("HDPE", False, False, set(), None),
            "Pallets": ("PLASTIC_PALLETS", False, False, set(), None),
            "HDPE Drums": ("HDPE", "DRUMS", False, set(), None),
            "Explicit HMW-HDPE Drums": ("HDPE_HMW", "DRUMS", False, set(), None),
            "LDPE Film": ("LDPE", "FILM", False, set(), None),
            "LDPE Film A": ("LDPE", "FILM", False, set(), "A"),
            "3-7 Commingled": ("3_7_COMMINGLED_BOTTLES", "BOTTLES", False, set(), None),
            "1-7 Commingled": ("1_7_COMMINGLED_BOTTLES", "BOTTLES", False, set(), None),
            "HDPE Drums (HMW-HDPE)": ("HDPE_HMW", "DRUMS", False, set(), None),
            "PP Supersacs": ("PP", False, False, set(), None),
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase=phrase):
                result = normalize_material(self.env, f"  {phrase}  ")
                polymer, form, source, attributes, grade = expected
                self.assertFalse(result.unresolved)
                self.assertEqual(result.source_description, phrase)
                self.assertEqual(result.polymer.code, polymer)
                self.assertEqual(result.form.code if result.form else False, form)
                self.assertEqual(result.source_type.code if result.source_type else False, source)
                self.assertEqual(set(result.attributes.mapped("code")), attributes)
                self.assertEqual(result.grade, grade)
                self.assertNotEqual(result.polymer.code, "OTHER")

        grade_only = normalize_material(self.env, "LDPE Film A")
        self.assertEqual(grade_only.grade, "A")
        self.assertFalse(grade_only.attributes)
        three = normalize_material(self.env, "3-7 Commingled Bottles")
        one = normalize_material(self.env, "1-7 Commingled Bottles")
        self.assertNotEqual(three.polymer, one.polymer)
        self.assertEqual(three.source_type.code, "POST_CONSUMER")
        self.assertEqual(one.source_type.code, "POST_CONSUMER")

        unknown = normalize_material(self.env, "mystery fluff")
        self.assertEqual(unknown.unresolved, ("unresolved material",))
        self.assertFalse(unknown.polymer)
        self.assertFalse(unknown.form)
        self.assertFalse(unknown.source_type)
        self.assertFalse(unknown.attributes)
        self.assertFalse(unknown.grade)
        self.assertEqual(unknown.source_description, "mystery fluff")

        contained = normalize_material(self.env, "something PE something")
        self.assertFalse(contained.polymer)

        conflict = normalize_material(self.env, "99 Clear LDPE Film", grade_evidence="95 Clear LDPE Film")
        self.assertEqual(conflict.unresolved, ("conflicting material evidence",))
        self.assertFalse(conflict.polymer)
        self.assertFalse(conflict.attributes)

    def test_new_polymer_masters_project_onto_the_stored_code(self):
        for code in ("PC_ABS", "3_7_COMMINGLED_BOTTLES", "1_7_COMMINGLED_BOTTLES"):
            found = self.env["plasticos.polymer"].search([("code", "=", code)])
            self.assertEqual(len(found), 1, code)
        self.assertTrue(self.env["plasticos.polymer"].search([("code", "=", "PC")], limit=1))
        self.assertTrue(self.env["plasticos.polymer"].search([("code", "=", "ABS")], limit=1))
        polymer = self.env["plasticos.polymer"].search([("code", "=", "PC_ABS")], limit=1)
        profile = self.env["plasticos.material.profile"].create(
            {"partner_id": self.partner.id, "polymer_id": polymer.id}
        )
        self.assertEqual(profile.polymer, "PC_ABS")
        bottles = self.env["plasticos.polymer"].search([("code", "=", "3_7_COMMINGLED_BOTTLES")], limit=1)
        other = self.env["plasticos.material.profile"].create({"partner_id": self.partner.id, "polymer_id": bottles.id})
        self.assertEqual(other.polymer, "3_7_COMMINGLED_BOTTLES")
