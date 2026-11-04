"""Approved material phrases resolve to existing masters and nothing else."""

from pathlib import Path
from unittest.mock import patch

from odoo.addons.plasticos_material_profile.models.material_normalizer import (
    normalize_crm_material,
    normalize_material,
)
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
        # The nine polymers the operator approved on 2026-11-03 are seeded and project too.
        for code in ("TPU", "TPV", "PVB", "PU_FOAM", "TEXTILE", "UBC", "FIBERGLASS", "WOOD_PALLETS", "AUTO_PARTS"):
            seeded = self.env["plasticos.polymer"].search([("code", "=", code)])
            self.assertEqual(len(seeded), 1, code)
            approved = self.env["plasticos.material.profile"].create(
                {"partner_id": self.partner.id, "polymer_id": seeded.id}
            )
            self.assertEqual(approved.polymer, code)

    def test_bare_ldpe_stays_unresolved_for_the_worksheet_resolver(self):
        with patch(
            "odoo.addons.plasticos_material_profile.models.material_normalizer._master",
        ) as lookup:
            result = normalize_material(self.env, "LDPE")
        self.assertFalse(lookup.called)
        self.assertEqual(result.unresolved, ("unresolved material",))
        self.assertFalse(result.polymer)
        self.assertFalse(result.form)

    def test_crm_exact_identities_do_not_change_worksheet_phrases(self):
        bare = normalize_crm_material(self.env, "  LDPE  ")
        self.assertFalse(bare.unresolved)
        self.assertEqual(bare.polymer.code, "LDPE")
        self.assertEqual(bare.form.code, "FILM")
        self.assertFalse(bare.grade)
        self.assertFalse(bare.attributes)
        self.assertFalse(bare.source_type)

        film = normalize_crm_material(self.env, "LDPE Film")
        self.assertEqual(film.polymer.code, "LDPE")
        self.assertEqual(film.form.code, "FILM")
        self.assertFalse(film.grade)

        drums = normalize_crm_material(self.env, "HDPE Drums")
        self.assertEqual((drums.polymer.code, drums.form.code), ("HDPE", "DRUMS"))
        alloy = normalize_crm_material(self.env, "PC/ABS")
        self.assertEqual(alloy.polymer.code, "PC_ABS")
        self.assertFalse(alloy.form)

        self.assertEqual(normalize_crm_material(self.env, "Nylon").polymer.code, "NYLON")
        self.assertEqual(normalize_crm_material(self.env, "Metal").polymer.code, "METAL")
        self.assertEqual(normalize_crm_material(self.env, "E-Waste").polymer.code, "EWASTE")
        hdpe = normalize_crm_material(self.env, "HDPE-")
        hmw = normalize_crm_material(self.env, "HDPE-HMW")
        self.assertEqual(hdpe.polymer.code, "HDPE")
        self.assertFalse(hdpe.form)
        self.assertEqual(hmw.polymer.code, "HDPE_HMW")
        self.assertFalse(hmw.form)
        self.assertNotEqual(hdpe.polymer, hmw.polymer)

        for phrase, code in (
            ("HDPE", "HDPE"),
            ("HDPE-HMW", "HDPE_HMW"),
            ("BOPP", "BOPP"),
            ("LLDPE", "LLDPE"),
            ("Plastic Pallets", "PLASTIC_PALLETS"),
            ("Gaylord Boxes", "GAYLORD_BOXES"),
        ):
            with self.subTest(phrase=phrase):
                result = normalize_crm_material(self.env, phrase)
                self.assertFalse(result.unresolved)
                self.assertEqual(result.polymer.code, code)
                self.assertFalse(result.form)

        prefixed = normalize_crm_material(self.env, "LDPE fluff")
        self.assertEqual(prefixed.unresolved, ("unresolved material",))
        self.assertFalse(prefixed.polymer)

        hinted = normalize_crm_material(self.env, "Nylon", structured={"Material Form": "LDPE"})
        self.assertEqual(hinted.polymer.code, "NYLON")
        self.assertFalse(hinted.form)

        conflict = normalize_crm_material(self.env, "HDPE", structured={"Material Form": "HDPE Drums"})
        self.assertEqual(conflict.unresolved, ("conflicting material evidence",))
        self.assertFalse(conflict.polymer)

    def test_approved_vanillasoft_aliases_resolve_every_master(self):
        from odoo.addons.plasticos_material_profile.models.material_normalizer import _CRM_ALIASES  # noqa: PLC0415

        for phrase in _CRM_ALIASES:
            with self.subTest(phrase=phrase):
                self.assertFalse(normalize_crm_material(self.env, phrase).unresolved)

        for phrase, polymer, form, grade in (
            ("PET Bottles", "PET", "BOTTLES", False),
            ("HDPE Bottles - Natural", "HDPE", "BOTTLES", False),
            ("HDPE Bottles - Z Bales", "HDPE", False, False),
            ("PP Supersacs (Lined)", "PP", False, False),
            ("IBC Totes (HMW-HDPE)", "HDPE_HMW", "TOTES", False),
            ("MRP Export", "MRP", False, False),
            ("LDPE Film B", "LDPE", "FILM", "B"),
            ("Acetal", "POM", False, False),
        ):
            with self.subTest(phrase=phrase):
                result = normalize_crm_material(self.env, phrase)
                self.assertEqual(result.polymer.code, polymer)
                self.assertEqual(result.form.code or False, form)
                self.assertEqual(result.grade or False, grade)
                self.assertFalse(result.attributes)

        for phrase, polymer, attribute in (
            ("HDPE Frac Melt", "HDPE", "frac_melt"),
            ("PVC Rigid", "PVC", "rigid"),
            ("LDPE Thick Gauge", "LDPE", "thick_gauge"),
        ):
            with self.subTest(phrase=phrase):
                result = normalize_crm_material(self.env, phrase)
                self.assertEqual(result.polymer.code, polymer)
                self.assertFalse(result.form)
                self.assertEqual(result.attributes.mapped("code"), [attribute])

        self.assertEqual(
            normalize_material(self.env, "PET Bottles").unresolved,
            ("unresolved material",),
        )
        self.assertEqual(
            normalize_crm_material(self.env, "Bottles (HD/PET)").unresolved,
            ("unresolved material",),
        )

    def test_worksheet_import_still_calls_normalize_material(self):
        source = (
            Path(__file__).resolve().parents[2] / "plasticos_transaction/models/native_document_import.py"
        ).read_text()
        self.assertIn("normalize_material(", source)
        self.assertNotIn("normalize_crm_material", source)
