"""The ERP product catalog resolves product names to existing masters and nothing else."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from odoo.addons.plasticos_material_profile.models import material_normalizer
from odoo.addons.plasticos_material_profile.models.material_normalizer import (
    ERP_PRODUCT_NOT_IN_CATALOG,
    ERP_PRODUCT_WITHOUT_POLYMER,
    erp_product_catalog,
    is_not_material,
    normalize_erp_product,
    normalize_material,
    phrase_table,
)
from odoo.tests import TransactionCase, tagged

HEADER = (
    "field_role,match_key,source_value,sources,erp_lines,vanillasoft_contacts,status,rule,polymer,material_grade,"
    "form,source_type,attributes,color,filler_type,process_type,quality_tier,packaging_type,is_plastic,confidence,note"
)
MASTER_MODELS = (
    "plasticos.polymer",
    "plasticos.material.grade",
    "plasticos.material.form",
    "plasticos.source.type",
    "plasticos.material.attribute",
    "plasticos.material.color",
    "plasticos.filler.type",
    "plasticos.packaging.type",
    "plasticos.material.quality.tier",
)


def _row(name, **cells):
    columns = HEADER.split(",")
    values = {"field_role": "material", "match_key": name.casefold(), "source_value": name, **cells}
    return ",".join(f'"{values.get(column, "")}"' for column in columns)


def _catalog(*rows):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "catalog.csv"
        path.write_text("\n".join((HEADER, *rows)) + "\n", encoding="utf-8")
        return material_normalizer._load_erp_catalog(path)


@tagged("post_install", "-at_install")
class TestErpProductCatalog(TransactionCase):
    def _master_counts(self):
        return {model: self.env[model].with_context(active_test=False).search_count([]) for model in MASTER_MODELS}

    def test_packaged_catalog_reads_blank_status_rows_by_product_name(self):
        catalog = erp_product_catalog()
        self.assertTrue(catalog)
        with_polymer = [entry for entry in catalog.values() if entry.spec is not None]
        without_polymer = [entry for entry in catalog.values() if entry.spec is None]
        self.assertTrue(with_polymer, "a blank status must not hide the mapped rows")
        self.assertTrue(without_polymer)
        for key, entry in catalog.items():
            self.assertEqual(key, " ".join(entry.source_value.split()).casefold())

    def test_packaged_rows_resolve_or_name_the_missing_master(self):
        before = self._master_counts()
        resolved = 0
        for entry in erp_product_catalog().values():
            with self.subTest(product=entry.source_value):
                result = normalize_erp_product(self.env, f"  {entry.source_value}  ")
                if entry.spec is None:
                    self.assertEqual(result.unresolved, (ERP_PRODUCT_WITHOUT_POLYMER,))
                    self.assertFalse(result.polymer)
                elif result.unresolved:
                    self.assertTrue(all(reason.startswith("missing ") for reason in result.unresolved))
                    self.assertFalse(result.polymer)
                else:
                    resolved += 1
                    self.assertEqual(result.polymer.code, entry.spec.polymer)
                    self.assertEqual(result.form.code or None, entry.spec.form)
                    self.assertEqual(result.material_grade.code or None, entry.spec.material_grade)
                    self.assertEqual(result.quality_tier.code or None, entry.quality_tier)
        self.assertTrue(resolved)
        self.assertEqual(self._master_counts(), before, "the catalog reader creates no master")

    def test_synthetic_row_resolves_every_slot(self):
        catalog = _catalog(
            _row(
                "Syn  HDPE Regrind",
                polymer="HDPE",
                form="REGRIND",
                source_type="POST_INDUSTRIAL",
                attributes="clean, washed",
                color="BLUE, WHITE",
                filler_type="glass",
                process_type="injection",
                quality_tier="GRADE_A",
                packaging_type="gaylords",
            )
        )
        with patch.object(material_normalizer, "_ERP_CATALOG", catalog):
            result = normalize_erp_product(self.env, "syn hdpe   REGRIND")
        self.assertFalse(result.unresolved)
        self.assertEqual(result.source_description, "syn hdpe REGRIND")
        self.assertEqual(result.polymer.code, "HDPE")
        self.assertEqual(result.form.code, "REGRIND")
        self.assertFalse(result.material_grade)
        self.assertEqual(result.source_type.code, "POST_INDUSTRIAL")
        self.assertEqual(set(result.attributes.mapped("code")), {"clean", "washed"})
        self.assertEqual(set(result.color.mapped("code")), {"BLUE", "WHITE"})
        self.assertEqual(result.filler_type.code, "glass")
        self.assertEqual(result.process_type, "injection")
        self.assertEqual(result.quality_tier.code, "GRADE_A")
        self.assertEqual(result.packaging_type.code, "gaylords")

    def test_unknown_product_no_polymer_and_missing_master_stay_unresolved(self):
        catalog = _catalog(
            _row("Syn No Polymer", material_grade="PALLETS"),
            _row("Syn Missing Tier", polymer="HDPE", quality_tier="SYN_NOT_A_TIER"),
            _row("Syn Missing Attribute", polymer="HDPE", attributes="clean SYN_NOT_AN_ATTRIBUTE"),
        )
        before = self._master_counts()
        with patch.object(material_normalizer, "_ERP_CATALOG", catalog):
            unknown = normalize_erp_product(self.env, "Syn Not Listed")
            no_polymer = normalize_erp_product(self.env, "Syn No Polymer")
            missing_tier = normalize_erp_product(self.env, "Syn Missing Tier")
            missing_attribute = normalize_erp_product(self.env, "Syn Missing Attribute")
            blank = normalize_erp_product(self.env, "   ")
        self.assertEqual(unknown.unresolved, (ERP_PRODUCT_NOT_IN_CATALOG,))
        self.assertEqual(blank.unresolved, (ERP_PRODUCT_NOT_IN_CATALOG,))
        self.assertEqual(no_polymer.unresolved, (ERP_PRODUCT_WITHOUT_POLYMER,))
        self.assertEqual(missing_tier.unresolved, ("missing plasticos.material.quality.tier SYN_NOT_A_TIER",))
        self.assertEqual(missing_attribute.unresolved, ("missing plasticos.material.attribute SYN_NOT_AN_ATTRIBUTE",))
        for result in (unknown, blank, no_polymer, missing_tier, missing_attribute):
            self.assertFalse(result.polymer)
            self.assertFalse(result.quality_tier)
        self.assertEqual(self._master_counts(), before)

    def test_duplicate_product_name_fails_the_load(self):
        with self.assertRaises(ValueError):
            _catalog(_row("Syn Twice", polymer="HDPE"), _row("syn  twice", polymer="LDPE"))

    def test_catalog_does_not_feed_the_phrase_sheet(self):
        phrases = phrase_table()
        only_in_catalog = [
            entry.source_value
            for key, entry in erp_product_catalog().items()
            if entry.spec is not None and key not in phrases and not is_not_material(key)
        ]
        self.assertTrue(only_in_catalog, "the catalog names products the phrase sheet does not")
        for product in only_in_catalog:
            with self.subTest(product=product):
                result = normalize_material(self.env, product)
                self.assertEqual(result.unresolved, ("unresolved material",))
                self.assertFalse(result.polymer)
                self.assertIsNone(result.quality_tier)
