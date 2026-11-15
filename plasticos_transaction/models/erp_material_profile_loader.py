"""Material profiles for ERP site partners, from two operator files.

Each input row names a product, a company, and a ship label. The product is
read through the ERP product catalog (``plasticos_material_profile``,
``data/ERP-Products.csv``). The partner is the ERP site child of the company
whose ``erp_address_label`` equals the ship label, or the company itself when
it has no ERP site children at all. Anything else is rejected with one reason
and writes nothing.

The supplier file and the customer file are one list. Which file a row came
from carries no meaning and is stored nowhere.

The loader creates no partner, no master, and no facility profile, and it does
not commit. The caller owns the transaction.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from odoo import Command, api, models

_logger = logging.getLogger(__name__)

# The ERP import owns these identities (plasticos_partner_import/models/erp_import_service.py).
XMLID_MODULE = "plasticos_transaction"
COMPANY_PREFIX = "legacy_erp_cp_"
SITE_PREFIX = "legacy_erp_address_"

BUCKET = "material_profiles"
SOURCE_TABLE = "ERP-Material-Profiles"
SUMMARY_SOURCE = "erp_material_profiles"
NOTE_PREFIX = "ERP product: "

BLANK_PRODUCT = "blank product"
PRODUCT_NOT_IN_CATALOG = "product not in catalog"
CATALOG_ROW_WITHOUT_POLYMER = "catalog row without polymer"
MISSING_MASTER = "missing master"
COMPANY_NOT_FOUND = "company not found"
COMPANY_AMBIGUOUS = "company ambiguous"
SITE_NOT_FOUND = "site not found"
SITE_AMBIGUOUS = "site ambiguous"
REJECT_REASONS = (
    BLANK_PRODUCT,
    PRODUCT_NOT_IN_CATALOG,
    CATALOG_ROW_WITHOUT_POLYMER,
    MISSING_MASTER,
    COMPANY_NOT_FOUND,
    COMPANY_AMBIGUOUS,
    SITE_NOT_FOUND,
    SITE_AMBIGUOUS,
)

PRODUCT_HEADER = "product"
COMPANY_HEADERS = ("supplier", "customer")
SHIP_HEADERS = ("ship from", "ship to")

# Profile field and the attribute of the resolved product that fills it.
# A value already on the profile is kept; a different one is an anomaly.
SINGLE_VALUED = (
    ("source_type_id", "source_type"),
    ("filler_type_id", "filler_type"),
    ("origin_process_type", "process_type"),
    ("quality_tier_id", "quality_tier"),
    ("packaging_type_id", "packaging_type"),
)


class _DryRun(Exception):  # noqa: N818 - control flow that rolls the savepoint back, not an error
    pass


def _norm(value) -> str:
    """Whitespace-collapsed and case-folded. The only equality the loader uses."""
    return " ".join(str(value or "").split()).casefold()


def _collapse(value) -> str:
    return " ".join(str(value or "").split())


def _decode(raw: bytes) -> str:
    """The operator files are Windows-1252. A UTF-8 file is read as UTF-8."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def _one_header(headers: dict[str, str], names: tuple[str, ...], path) -> str:
    found = [headers[name] for name in names if name in headers]
    if len(found) != 1:
        wanted = " or ".join(repr(name) for name in names)
        raise ValueError(f"{Path(path).name}: expected exactly one column named {wanted}")
    return found[0]


def read_rows(path) -> list[dict]:
    """Rows of one operator file as ``{ref, product, company, ship}``.

    ``ref`` is ``<file name>:<line>``. It names the row without repeating a
    company or a site.
    """
    reader = csv.DictReader(io.StringIO(_decode(Path(path).read_bytes()), newline=""))
    headers = {_norm(name): name for name in reader.fieldnames or [] if name}
    product = _one_header(headers, (PRODUCT_HEADER,), path)
    company = _one_header(headers, COMPANY_HEADERS, path)
    ship = _one_header(headers, SHIP_HEADERS, path)
    name = Path(path).name
    return [
        {
            "ref": f"{name}:{reader.line_num}",
            "product": _collapse(row.get(product)),
            "company": row.get(company),
            "ship": row.get(ship),
        }
        for row in reader
    ]


def _reject_reason(unresolved) -> str:
    """One loader reason for a product the catalog reader left unresolved."""
    for reason in (PRODUCT_NOT_IN_CATALOG, CATALOG_ROW_WITHOUT_POLYMER):
        if reason in unresolved:
            return reason
    return MISSING_MASTER


class PlasticosErpMaterialProfileLoader(models.AbstractModel):
    """Create or reuse material profiles on ERP site partners. Stores nothing itself."""

    _name = "plasticos.erp.material.profile.loader"
    _description = "ERP Material Profile Loader"

    @api.model
    def load(self, paths, dry_run=False) -> dict:
        """Load every file in ``paths`` as one list and return the run report.

        ``report["summary"]`` is the shared import-run summary, in which
        ``records_seen == created + updated + unchanged + rejected``. A dry run
        resolves and counts exactly as an applied run does, then rolls back.
        """
        from odoo.addons.plasticos_partner_import.erp import summary as import_summary  # noqa: PLC0415
        from odoo.addons.plasticos_partner_import.erp.report import ImportReport  # noqa: PLC0415

        started = import_summary.utc_now()
        rows = [row for path in paths for row in read_rows(path)]
        report = ImportReport()
        report.counts[BUCKET] = dict.fromkeys(("created", "updated", "skipped", "rejected"), 0)
        report.source_counts[SOURCE_TABLE] = len(rows)
        try:
            with self.env.cr.savepoint():
                self._load_rows(rows, report)
                if dry_run:
                    raise _DryRun
        except _DryRun:
            self.env.invalidate_all()
        result = report.as_dict()
        result["dry_run"] = bool(dry_run)
        summary = import_summary.import_run_summary(result, start_time=started)
        summary["source"] = SUMMARY_SOURCE
        result["summary"] = summary
        result["rejected_by_reason"] = {
            reason: count
            for reason in REJECT_REASONS
            if (count := sum(1 for row in report.unresolved if row["kind"] == reason))
        }
        return result

    def _load_rows(self, rows, report) -> None:
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            erp_product_catalog,
            normalize_erp_product,
        )

        companies, sites = self._erp_partner_index()
        resolved_products: dict[str, object] = {}
        for row in rows:
            product = row["product"]
            if not product:
                self._reject(report, row, BLANK_PRODUCT)
                continue
            key = _norm(product)
            material = resolved_products.get(key)
            if material is None:
                material = resolved_products[key] = normalize_erp_product(self.env, product)
            if material.unresolved:
                self._reject(report, row, _reject_reason(material.unresolved), "; ".join(material.unresolved))
                continue
            partner, reason = self._resolve_partner(companies, sites, row["company"], row["ship"])
            if reason:
                self._reject(report, row, reason)
                continue
            # The note carries the catalog's spelling, so one product is one line however a file cases it.
            outcome = self._apply(partner, material, erp_product_catalog()[key].source_value, row, report)
            report.bump(BUCKET, outcome)

    @staticmethod
    def _reject(report, row, reason, detail=None) -> None:
        """One rejected source row. It is counted once, through ``unresolved``."""
        report.unresolved_ref(SOURCE_TABLE, reason, row["ref"], detail or reason)

    # ── Partner resolution ───────────────────────────────────────────────────

    def _marked_partner_ids(self, prefix: str) -> list[int]:
        data = self.env["ir.model.data"].search(
            [("module", "=", XMLID_MODULE), ("model", "=", "res.partner"), ("name", "=like", prefix + "%")]
        )
        return data.mapped("res_id")

    def _erp_partner_index(self):
        """ERP companies by normalised name, and ERP site children by company id.

        An address the ERP import folded into its company carries the company's
        own id under a site marker. It is the company, not a site child.
        """
        Partner = self.env["res.partner"].with_context(active_test=False)
        companies = Partner.browse(self._marked_partner_ids(COMPANY_PREFIX)).exists()
        sites = Partner.browse(self._marked_partner_ids(SITE_PREFIX)).exists() - companies
        by_name: dict[str, list[int]] = {}
        for company in companies:
            name = _norm(company.name)
            if name:
                by_name.setdefault(name, []).append(company.id)
        by_company: dict[int, list[int]] = {}
        for site in sites:
            if site.parent_id in companies:
                by_company.setdefault(site.parent_id.id, []).append(site.id)
        return by_name, by_company

    def _resolve_partner(self, companies, sites, company_value, ship_value):
        """Return ``(partner, None)`` or ``(empty, reason)``. Never a best guess."""
        Partner = self.env["res.partner"].with_context(active_test=False)
        name = _norm(company_value)
        matches = companies.get(name, []) if name else []
        if not matches:
            return Partner.browse(), COMPANY_NOT_FOUND
        if len(matches) > 1:
            return Partner.browse(), COMPANY_AMBIGUOUS
        company = Partner.browse(matches[0])
        site_ids = sites.get(company.id)
        if not site_ids:
            return company, None
        label = _norm(ship_value)
        hits = Partner.browse(site_ids).filtered(lambda site: label and _norm(site.erp_address_label) == label)
        if not hits:
            return Partner.browse(), SITE_NOT_FOUND
        if len(hits) > 1:
            return Partner.browse(), SITE_AMBIGUOUS
        return hits, None

    # ── Profile write ────────────────────────────────────────────────────────

    def _apply(self, partner, material, product, row, report) -> str:
        """Create or reuse the profile on its unique key. Returns the count bucket."""
        from odoo.addons.plasticos_partner_import.models.erp_import_service import IMPORT_CONTEXT  # noqa: PLC0415

        Profile = self.env["plasticos.material.profile"].with_context(active_test=False, **IMPORT_CONTEXT)
        note = NOTE_PREFIX + product
        profile = Profile.search(
            [
                ("partner_id", "=", partner.id),
                ("polymer_id", "=", material.polymer.id),
                ("form_id", "=", material.form.id or False),
                ("material_grade_id", "=", material.material_grade.id or False),
            ],
            limit=1,
        )
        if not profile:
            values = {
                "partner_id": partner.id,
                "polymer_id": material.polymer.id,
                "form_id": material.form.id or False,
                "material_grade_id": material.material_grade.id or False,
                "color_ids": [Command.set(material.color.ids)],
                "material_attribute_ids": [Command.set(material.attributes.ids)],
                "freeform_notes": note,
            }
            for field, attribute in SINGLE_VALUED:
                values[field] = self._field_value(getattr(material, attribute))
            Profile.create(values)
            return "created"

        values = {}
        new_colors = material.color - profile.color_ids
        if new_colors:
            values["color_ids"] = [Command.link(color.id) for color in new_colors]
        new_attributes = material.attributes - profile.material_attribute_ids
        if new_attributes:
            values["material_attribute_ids"] = [Command.link(attribute.id) for attribute in new_attributes]
        for field, attribute in SINGLE_VALUED:
            wanted = self._field_value(getattr(material, attribute))
            if not wanted:
                continue
            current = self._field_value(profile[field])
            if not current:
                values[field] = wanted
            elif current != wanted:
                report.anomaly(
                    SOURCE_TABLE, row["ref"], f"profile {profile.id}: {field} already set to a different value; kept"
                )
        lines = (profile.freeform_notes or "").splitlines()
        if note not in [line.strip() for line in lines]:
            values["freeform_notes"] = "\n".join([*lines, note])
        if not values:
            return "skipped"
        profile.write(values)
        return "updated"

    @staticmethod
    def _field_value(value):
        """A record as its id, a selection code as itself, empty as False."""
        if isinstance(value, models.BaseModel):
            return value.id or False
        return value or False
