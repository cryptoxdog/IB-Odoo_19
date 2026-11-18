"""ERP material-profile loader against the real ORM.

Every partner, ERP id, product name, and file here is synthetic. The catalog is
a synthetic file too, so the packaged ``ERP-Products.csv`` can change without
changing what these tests prove.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from odoo.addons.plasticos_material_profile.models import material_normalizer
from odoo.tests import TransactionCase, tagged

from ..models import erp_material_profile_loader as loader

CATALOG_HEADER = (
    "field_role,match_key,source_value,sources,erp_lines,vanillasoft_contacts,status,rule,polymer,material_grade,"
    "form,source_type,attributes,color,filler_type,process_type,quality_tier,packaging_type,is_plastic,confidence,note"
)
SUPPLIERS = "Syn-Suppliers.csv"
CUSTOMERS = "Syn-Customers.csv"


def _catalog_row(name, **cells):
    values = {"field_role": "material", "match_key": name.casefold(), "source_value": name, **cells}
    return ",".join(f'"{values.get(column, "")}"' for column in CATALOG_HEADER.split(","))


CATALOG_ROWS = (
    _catalog_row(
        "Syn HDPE Regrind",
        polymer="HDPE",
        form="REGRIND",
        source_type="POST_INDUSTRIAL",
        attributes="clean",
        color="BLUE",
        packaging_type="gaylords",
    ),
    _catalog_row(
        "Syn HDPE Regrind Washed",
        polymer="HDPE",
        form="REGRIND",
        source_type="POST_CONSUMER",
        attributes="washed",
        color="BLUE, WHITE",
        process_type="injection",
        quality_tier="GRADE_A",
    ),
    _catalog_row("Syn LDPE Film", polymer="LDPE", form="FILM"),
    _catalog_row("Syn No Polymer", material_grade="PALLETS"),
    _catalog_row("Syn Missing Master", polymer="HDPE", attributes="SYN_NOT_AN_ATTRIBUTE"),
)


@tagged("post_install", "-at_install")
class TestErpMaterialProfileLoader(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Loader = cls.env["plasticos.erp.material.profile.loader"]
        cls.Profile = cls.env["plasticos.material.profile"].with_context(active_test=False)
        cls._folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._folder.cleanup)
        cls.folder = Path(cls._folder.name)
        catalog_path = cls.folder / "catalog.csv"
        catalog_path.write_text("\n".join((CATALOG_HEADER, *CATALOG_ROWS)) + "\n", encoding="utf-8")
        catalog = material_normalizer._load_erp_catalog(catalog_path)
        patcher = patch.object(material_normalizer, "_ERP_CATALOG", catalog)
        patcher.start()
        cls.addClassCleanup(patcher.stop)

        cls.resins = cls._company("Synthetic Resins Co", "990001")
        cls.plant = cls._site(cls.resins, "Synthetic Resins Co - Plant", "880001", "Plant 1")
        cls.warehouse = cls._site(cls.resins, "Synthetic Resins Co - Warehouse", "880002", "Warehouse")
        cls.solo = cls._company("Synthetic Solo LLC", "990002")
        # An address the ERP import folded into its company: the site marker names the company.
        cls._mark(cls.solo, f"{loader.SITE_PREFIX}880003")
        cls.twin_a = cls._company("Synthetic Twin Inc", "990003")
        cls.twin_b = cls._company("Synthetic Twin Inc", "990004")
        cls.echo = cls._company("Synthetic Echo Sites", "990005")
        cls._site(cls.echo, "Synthetic Echo Sites - A", "880004", "Main")
        cls._site(cls.echo, "Synthetic Echo Sites - B", "880005", "Main")
        cls.accent = cls._company("Synthétic Accent Co", "990006")
        # Same name as an ERP company, but not an ERP counterparty: never a target.
        cls.env["res.partner"].create({"name": "Synthetic Solo LLC", "is_company": True})

    @classmethod
    def _mark(cls, partner, name):
        cls.env["ir.model.data"].create(
            {
                "module": loader.XMLID_MODULE,
                "name": name,
                "model": "res.partner",
                "res_id": partner.id,
                "noupdate": True,
            }
        )

    @classmethod
    def _company(cls, name, cp_id):
        partner = cls.env["res.partner"].create({"name": name, "is_company": True})
        cls._mark(partner, f"{loader.COMPANY_PREFIX}{cp_id}")
        return partner

    @classmethod
    def _site(cls, company, name, address_id, label):
        partner = cls.env["res.partner"].create(
            {"name": name, "parent_id": company.id, "is_company": True, "erp_address_label": label}
        )
        cls._mark(partner, f"{loader.SITE_PREFIX}{address_id}")
        return partner

    def _files(self, suppliers=(), customers=(), encoding="utf-8"):
        """Write the two operator files. Each row is ``(product, company, ship)``."""
        paths = []
        for name, header, rows in (
            (SUPPLIERS, "Product,Supplier,Ship From", suppliers),
            (CUSTOMERS, "Product,Customer,Ship To", customers),
        ):
            path = self.folder / name
            lines = [header, *(",".join(f'"{cell}"' for cell in row) for row in rows)]
            path.write_bytes(("\r\n".join(lines) + "\r\n").encode(encoding))
            paths.append(str(path))
        return paths

    def _run(self, paths, dry_run=False):
        report = self.Loader.load(paths, dry_run=dry_run)
        summary = report["summary"]
        self.assertEqual(
            summary["records_seen"],
            summary["records_created"]
            + summary["records_updated"]
            + summary["records_unchanged"]
            + summary["records_rejected"],
        )
        self.assertNotEqual(summary["final_status"], "failed")
        self.assertEqual(summary["duplicates"], 0)
        self.assertEqual(summary["source"], loader.SUMMARY_SOURCE)
        self.assertEqual(sum(report["rejected_by_reason"].values()), summary["records_rejected"])
        return report

    def _profiles(self, partners):
        return self.Profile.search([("partner_id", "in", partners.ids)])

    def test_row_lands_on_the_matching_site_child(self):
        paths = self._files(suppliers=[("Syn  HDPE regrind", "  synthetic RESINS co ", "plant   1")])
        report = self._run(paths)
        self.assertEqual(report["summary"]["records_created"], 1)
        self.assertEqual(report["summary"]["records_rejected"], 0)
        self.assertEqual(report["summary"]["final_status"], "success")
        profile = self._profiles(self.plant)
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile.polymer_id.code, "HDPE")
        self.assertEqual(profile.form_id.code, "REGRIND")
        self.assertFalse(profile.material_grade_id)
        self.assertEqual(profile.source_type_id.code, "POST_INDUSTRIAL")
        self.assertEqual(profile.color_ids.mapped("code"), ["BLUE"])
        self.assertEqual(profile.material_attribute_ids.mapped("code"), ["clean"])
        self.assertEqual(profile.packaging_type_id.code, "gaylords")
        self.assertEqual(profile.freeform_notes, "ERP product: Syn HDPE Regrind")
        self.assertEqual(profile.direction, "out")
        self.assertFalse(self._profiles(self.resins | self.warehouse))

    def test_supplier_list_is_out_and_customer_list_is_in(self):
        paths = self._files(
            suppliers=[("Syn HDPE Regrind", "Synthetic Resins Co", "Plant 1")],
            customers=[
                ("Syn HDPE Regrind", "Synthetic Resins Co", "Plant 1"),
                ("Syn LDPE Film", "Synthetic Resins Co", "Warehouse"),
            ],
        )
        report = self._run(paths)
        self.assertEqual(report["summary"]["records_seen"], 3)
        self.assertEqual(report["summary"]["records_created"], 3)
        self.assertEqual(report["summary"]["records_unchanged"], 0)
        plant = self._profiles(self.plant)
        self.assertEqual(set(plant.mapped("direction")), {"out", "in"})
        self.assertEqual(set(plant.mapped("polymer_id.code")), {"HDPE"})
        warehouse = self._profiles(self.warehouse)
        self.assertEqual(warehouse.direction, "in")
        self.assertEqual(warehouse.polymer_id.code, "LDPE")

        self.env.flush_all()
        with (
            patch.object(type(self.Profile), "write") as write,
            patch.object(type(self.Profile), "create") as create,
        ):
            replay = self._run(paths)
        write.assert_not_called()
        create.assert_not_called()
        self.assertEqual(replay["summary"]["records_created"], 0)
        self.assertEqual(replay["summary"]["records_updated"], 0)
        self.assertEqual(replay["summary"]["records_unchanged"], 3)
        self.assertEqual(self._profiles(self.plant | self.warehouse), plant | warehouse)

    def test_second_run_creates_and_changes_nothing(self):
        paths = self._files(
            suppliers=[
                ("Syn HDPE Regrind", "Synthetic Resins Co", "Plant 1"),
                ("Syn HDPE Regrind Washed", "Synthetic Resins Co", "Plant 1"),
                ("Syn LDPE Film", "Synthetic Solo LLC", ""),
                ("Syn Not Listed", "Synthetic Resins Co", "Plant 1"),
            ]
        )
        first = self._run(paths)
        self.assertEqual(first["summary"]["records_created"], 2)
        self.assertEqual(first["summary"]["records_updated"], 1)
        self.assertEqual(first["summary"]["records_rejected"], 1)
        partners = self.resins | self.plant | self.warehouse | self.solo
        profiles = self._profiles(partners)
        self.env.flush_all()
        fields = ["freeform_notes", "color_ids", "material_attribute_ids", *(name for name, _ in loader.SINGLE_VALUED)]
        before = profiles.read(fields)

        with (
            patch.object(type(self.Profile), "write") as write,
            patch.object(type(self.Profile), "create") as create,
        ):
            second = self._run(paths)
        write.assert_not_called()
        create.assert_not_called()
        self.assertEqual(second["summary"]["records_created"], 0)
        self.assertEqual(second["summary"]["records_updated"], 0)
        self.assertEqual(second["summary"]["records_unchanged"], 3)
        self.assertEqual(second["summary"]["records_rejected"], 1)
        self.assertEqual(self._profiles(partners), profiles)
        self.assertEqual(profiles.read(fields), before)

    def test_rejected_rows_write_nothing_and_carry_their_reason(self):
        rows = [
            ("Syn HDPE Regrind", "Synthetic Resins Co", "Plant 9"),
            ("Syn Not Listed", "Synthetic Resins Co", "Plant 1"),
            ("Syn No Polymer", "Synthetic Resins Co", "Plant 1"),
            ("", "Synthetic Resins Co", "Plant 1"),
            ("Syn Missing Master", "Synthetic Resins Co", "Plant 1"),
            ("Syn HDPE Regrind", "Synthetic Nobody Ltd", "Plant 1"),
            ("Syn HDPE Regrind", "Synthetic Twin Inc", ""),
            ("Syn HDPE Regrind", "Synthetic Echo Sites", "Main"),
            ("Syn HDPE Regrind", "Synthetic Resins Co", ""),
        ]
        before = self.Profile.search_count([])
        report = self._run(self._files(suppliers=rows))
        self.assertEqual(self.Profile.search_count([]), before)
        summary = report["summary"]
        self.assertEqual(summary["records_seen"], len(rows))
        self.assertEqual(summary["records_rejected"], len(rows))
        self.assertEqual(summary["records_created"] + summary["records_updated"] + summary["records_unchanged"], 0)
        self.assertEqual(summary["final_status"], "partial")
        reasons = {row["key"]: row["kind"] for row in report["unresolved"]}
        self.assertEqual(
            reasons,
            {
                f"{SUPPLIERS}:2": loader.SITE_NOT_FOUND,
                f"{SUPPLIERS}:3": loader.PRODUCT_NOT_IN_CATALOG,
                f"{SUPPLIERS}:4": loader.CATALOG_ROW_WITHOUT_POLYMER,
                f"{SUPPLIERS}:5": loader.BLANK_PRODUCT,
                f"{SUPPLIERS}:6": loader.MISSING_MASTER,
                f"{SUPPLIERS}:7": loader.COMPANY_NOT_FOUND,
                f"{SUPPLIERS}:8": loader.COMPANY_AMBIGUOUS,
                f"{SUPPLIERS}:9": loader.SITE_AMBIGUOUS,
                f"{SUPPLIERS}:10": loader.SITE_NOT_FOUND,
            },
        )
        self.assertEqual(report["rejected_by_reason"][loader.SITE_NOT_FOUND], 2)
        self.assertEqual(len(summary["errors"]), len(rows))
        for error in summary["errors"]:
            self.assertNotIn("Synthetic", error["message"])

    def test_company_without_erp_sites_receives_the_profile_itself(self):
        paths = self._files(
            suppliers=[("Syn LDPE Film", "Synthetic Solo LLC", "Any Label")],
            customers=[("Syn LDPE Film", "Synthétic Accent Co", "")],
            encoding="cp1252",
        )
        report = self._run(paths)
        self.assertEqual(report["summary"]["records_created"], 2)
        self.assertEqual(report["summary"]["records_rejected"], 0)
        self.assertEqual(self._profiles(self.solo).polymer_id.code, "LDPE")
        self.assertEqual(self._profiles(self.solo).direction, "out")
        self.assertEqual(self._profiles(self.accent).form_id.code, "FILM")
        self.assertEqual(self._profiles(self.accent).direction, "in")

    def test_products_sharing_a_key_at_one_site_yield_one_profile(self):
        paths = self._files(
            suppliers=[
                ("Syn HDPE Regrind", "Synthetic Resins Co", "Plant 1"),
                ("Syn HDPE Regrind Washed", "Synthetic Resins Co", "Plant 1"),
            ],
        )
        report = self._run(paths)
        self.assertEqual(report["summary"]["records_created"], 1)
        self.assertEqual(report["summary"]["records_updated"], 1)
        profile = self._profiles(self.plant)
        self.assertEqual(len(profile), 1)
        self.assertEqual(
            profile.freeform_notes.splitlines(),
            ["ERP product: Syn HDPE Regrind", "ERP product: Syn HDPE Regrind Washed"],
        )
        self.assertEqual(set(profile.color_ids.mapped("code")), {"BLUE", "WHITE"})
        self.assertEqual(set(profile.material_attribute_ids.mapped("code")), {"clean", "washed"})
        # Empty single-valued fields are filled; a value already there is kept and reported.
        self.assertEqual(profile.quality_tier_id.code, "GRADE_A")
        self.assertEqual(profile.origin_process_type, "injection")
        self.assertEqual(profile.packaging_type_id.code, "gaylords")
        self.assertEqual(profile.source_type_id.code, "POST_INDUSTRIAL")
        self.assertEqual(
            [(row["key"], row["detail"]) for row in report["anomalies"]],
            [(f"{SUPPLIERS}:3", f"profile {profile.id}: source_type_id already set to a different value; kept")],
        )
        self.assertEqual(profile.direction, "out")

    def test_existing_notes_are_kept_and_the_product_line_is_added_once(self):
        polymer = self.env["plasticos.polymer"].search([("code", "=", "LDPE")], limit=1)
        form = self.env["plasticos.material.form"].search([("code", "=", "FILM")], limit=1)
        existing = self.Profile.create(
            {
                "partner_id": self.warehouse.id,
                "polymer_id": polymer.id,
                "form_id": form.id,
                "freeform_notes": "Operator note",
            }
        )
        paths = self._files(suppliers=[("Syn LDPE Film", "Synthetic Resins Co", "warehouse")])
        self.assertEqual(self._run(paths)["summary"]["records_updated"], 1)
        self.assertEqual(self._run(paths)["summary"]["records_unchanged"], 1)
        self.assertEqual(self._profiles(self.warehouse), existing)
        self.assertEqual(existing.freeform_notes.splitlines(), ["Operator note", "ERP product: Syn LDPE Film"])
        self.assertEqual(existing.direction, "out")

    def test_dry_run_counts_like_an_applied_run_and_persists_nothing(self):
        paths = self._files(
            suppliers=[
                ("Syn HDPE Regrind", "Synthetic Resins Co", "Plant 1"),
                ("Syn Not Listed", "Synthetic Resins Co", "Plant 1"),
            ]
        )
        before = self.Profile.search_count([])
        dry = self._run(paths, dry_run=True)
        self.assertTrue(dry["dry_run"])
        self.assertEqual(dry["summary"]["records_created"], 1)
        self.assertEqual(dry["summary"]["records_rejected"], 1)
        self.assertEqual(self.Profile.search_count([]), before)
        applied = self._run(paths)
        self.assertEqual(applied["summary"]["records_created"], 1)
        self.assertEqual(self.Profile.search_count([]), before + 1)

    def test_one_capability_on_the_site_is_linked(self):
        facility = self.env["plasticos.facility.profile"].create({"partner_id": self.plant.id})
        cap_type = self.env["plasticos.capability.type"].search([("code", "=", "shredding")], limit=1)
        self.assertTrue(cap_type)
        only = self.env["plasticos.capability"].create(
            {"facility_profile_id": facility.id, "capability_type_id": cap_type.id}
        )
        self._run(self._files(suppliers=[("Syn LDPE Film", "Synthetic Resins Co", "Plant 1")]))
        profile = self._profiles(self.plant)
        self.assertEqual(len(profile), 1)
        self.assertEqual(profile.direction, "out")
        self.assertEqual(profile.capability_id, only)

    def test_a_file_without_the_expected_columns_is_refused(self):
        path = self.folder / "Syn-Bad.csv"
        path.write_text("Product,Supplier,Customer,Ship From\nSyn LDPE Film,A,B,C\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.Loader.load([str(path)])
