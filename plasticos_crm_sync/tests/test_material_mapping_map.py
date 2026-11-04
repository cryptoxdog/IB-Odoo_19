"""The committed VanillaSoft material map and the importer resolve every token the same way."""

import csv
from pathlib import Path

from odoo.addons.plasticos_material_profile.grade_codes import FORMER_FORM_CODES
from odoo.addons.plasticos_material_profile.models import material_normalizer
from odoo.addons.plasticos_material_profile.models.material_normalizer import normalize_material
from odoo.tests import TransactionCase, tagged


def normalize_crm_material(env, description, grade_evidence=None, structured=None):
    return normalize_material(env, description, grade_evidence=grade_evidence, structured=structured, crm_aliases=True)


MAP_FILE = Path(__file__).resolve().parents[1] / "data" / "vanillasoft_material_mapping.csv"
MATRIX_FILE = Path(__file__).resolve().parents[2] / "plasticos_material_profile" / "data" / "material_mapping.csv"


@tagged("post_install", "-at_install")
class TestVanillaSoftMaterialMap(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with MAP_FILE.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_mapped_tokens_resolve_to_the_listed_masters(self):
        mapped = [row for row in self.rows if row["status"] == "mapped"]
        self.assertTrue(mapped)
        for row in mapped:
            with self.subTest(token=row["source_token"]):
                result = normalize_crm_material(self.env, row["source_token"])
                self.assertFalse(result.unresolved)
                self.assertEqual(result.polymer.code, row["polymer"])
                if row["form"] in FORMER_FORM_CODES:
                    # IBC totes moved to their own IBC_TOTES grade.
                    self.assertFalse(result.form)
                    self.assertIn(row["form"], result.material_grade.code or "")
                else:
                    self.assertEqual(result.form.code or "", row["form"])
                self.assertEqual(result.grade or "", row["grade"])
                self.assertEqual(result.source_type.code or "", row["source_type"])
                self.assertEqual(sorted(result.attributes.mapped("code")), sorted(row["attributes"].split()))

    def test_unmapped_tokens_stay_unresolved(self):
        for row in self.rows:
            if row["status"] == "mapped":
                continue
            with self.subTest(token=row["source_token"], status=row["status"]):
                result = normalize_crm_material(self.env, row["source_token"])
                self.assertEqual(result.unresolved, ("unresolved material",))
                self.assertFalse(result.polymer)

    def test_every_importer_phrase_is_in_the_map(self):
        listed = {" ".join(row["source_token"].split()).casefold() for row in self.rows if row["status"] == "mapped"}
        with MATRIX_FILE.open(newline="", encoding="utf-8") as handle:
            matrix = {
                " ".join(row["match_key"].split()).casefold()
                for row in csv.DictReader(handle)
                if row["field_role"] == "material" and row["status"] == "mapped"
            }
        for table in ("_SPECS", "_CRM_EXACT", "_CRM_ALIASES"):
            for phrase in getattr(material_normalizer, table):
                with self.subTest(table=table, phrase=phrase):
                    self.assertTrue(phrase in listed or phrase in matrix, phrase)
