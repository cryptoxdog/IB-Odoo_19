"""The committed VanillaSoft material map and the importer resolve every token the same way."""

import csv
from pathlib import Path

from odoo.addons.plasticos_material_profile.models import material_normalizer
from odoo.addons.plasticos_material_profile.models.material_normalizer import normalize_crm_material
from odoo.tests import TransactionCase, tagged

MAP_FILE = Path(__file__).resolve().parents[1] / "data" / "vanillasoft_material_mapping.csv"


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
        for table in ("_SPECS", "_CRM_EXACT", "_CRM_ALIASES"):
            for phrase in getattr(material_normalizer, table):
                with self.subTest(table=table, phrase=phrase):
                    self.assertIn(phrase, listed)
