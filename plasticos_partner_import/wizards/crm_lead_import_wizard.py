"""
CRM Lead Import Wizard
Provides UI to trigger the VanillaSoft CRM lead import from CSV files.
"""

import logging
import os

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

DEFAULT_CRM_CSV = "tests/data/sample_vanillasoft_leads.csv"  # TODO: replace with real export
CONFIG_CRM_CSV = "plasticos_partner_import.default_crm_csv"


class CRMLeadImportWizard(models.TransientModel):
    _name = "plasticos.crm.lead.import.wizard"
    _description = "CRM Lead Import Wizard"

    crm_file = fields.Binary(
        string="CRM Leads CSV",
        help="CSV file with VanillaSoft CRM contacts. Leave empty to use default file in module.",
    )
    crm_filename = fields.Char(string="CRM Filename")

    use_default_file = fields.Boolean(
        string="Use Default CSV File",
        default=True,
        help="Use the CSV file included in the plasticos_partner_import module.",
    )

    dry_run = fields.Boolean(
        string="Dry Run",
        default=False,
        help="Validate file without creating records.",
    )

    skip_duplicates = fields.Boolean(
        string="Skip Duplicates",
        default=True,
        help="Skip leads that already exist (by VanillaSoft ContactID).",
    )

    result_message = fields.Text(
        string="Result",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Configure"),
            ("done", "Complete"),
        ],
        default="draft",
    )

    # Stats
    total_rows = fields.Integer(string="Total Rows", readonly=True)
    leads_created = fields.Integer(string="Leads Created", readonly=True)
    leads_skipped = fields.Integer(string="Leads Skipped", readonly=True)
    error_count = fields.Integer(string="Errors", readonly=True)

    def _get_module_path(self):
        """Get the path to the plasticos_partner_import module."""
        import odoo.modules.module as mod

        path = mod.get_module_path("plasticos_partner_import")
        if not path:
            raise UserError(_("Could not determine module path."))
        return path

    def _get_default_csv_path(self) -> str:
        """Resolve path for default CSV; ir.config_parameter overrides built-in path."""
        param = self.env["ir.config_parameter"].sudo()
        custom = param.get_param(CONFIG_CRM_CSV)
        if custom and os.path.isfile(custom):
            return custom
        return os.path.join(self._get_module_path(), DEFAULT_CRM_CSV)

    def _save_uploaded_file(self, binary_data, filename):
        """Save uploaded binary to temp file and return path."""
        import base64
        import tempfile

        if not binary_data:
            return None

        decoded = base64.b64decode(binary_data)
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "wb") as f:
            f.write(decoded)
        return path

    def _count_csv_rows(self, csv_path):
        """Count rows in CSV file (excluding header)."""
        with open(csv_path, encoding="utf-8-sig") as f:
            return sum(1 for _ in f) - 1

    def action_import(self):
        """Run the CRM lead import."""
        self.ensure_one()

        import_svc = self.env["plasticos.crm.lead.import.service"]
        csv_path = None
        temp_file = None

        try:
            if self.use_default_file:
                csv_path = self._get_default_csv_path()
                if not os.path.exists(csv_path):
                    raise UserError(_("Default CRM CSV not found: %s") % csv_path)
            else:
                if not self.crm_file:
                    raise UserError(_("Please upload a CRM CSV file."))
                csv_path = self._save_uploaded_file(self.crm_file, self.crm_filename)
                temp_file = csv_path

            self.total_rows = self._count_csv_rows(csv_path)

            if self.dry_run:
                self.result_message = (
                    f"Dry run complete.\nCSV file: {csv_path}\nTotal rows: {self.total_rows}\n\nNo records created."
                )
                self.state = "done"
                return self._return_wizard()

            _logger.info("Starting CRM lead import from: %s (%d rows)", csv_path, self.total_rows)

            result = import_svc.run_crm_lead_import(csv_path)

            self.leads_created = result.get("leads_created", 0)
            self.leads_skipped = result.get("leads_skipped", 0)
            self.error_count = len(result.get("errors", []))

            msg_parts = [
                "Import completed!",
                f"Total rows processed: {self.total_rows}",
                f"Leads created: {self.leads_created}",
                f"Leads skipped (duplicates): {self.leads_skipped}",
            ]

            if result.get("errors"):
                msg_parts.append(f"\nErrors: {self.error_count}")
                for err in result["errors"][:10]:
                    msg_parts.append(f"  - Row {err['row']}: {err['error']}")
                if len(result["errors"]) > 10:
                    msg_parts.append(f"  ... and {len(result['errors']) - 10} more")

            self.result_message = "\n".join(msg_parts)
            self.state = "done"

        finally:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return self._return_wizard()

    def _return_wizard(self):
        """Return action to keep wizard open with results."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_close(self):
        """Close the wizard."""
        return {"type": "ir.actions.act_window_close"}

    def action_view_leads(self):
        """Open the CRM leads list view."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Imported CRM Leads"),
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [("vanillasoft_id", "!=", False)],
            "context": {"search_default_filter_my_leads": 0},
        }

    def action_preview(self):
        """Preview first 10 rows of the CSV."""
        self.ensure_one()
        import csv

        csv_path = None
        temp_file = None

        try:
            if self.use_default_file:
                csv_path = self._get_default_csv_path()
                if not os.path.exists(csv_path):
                    raise UserError(_("Default CRM CSV not found: %s") % csv_path)
            else:
                if not self.crm_file:
                    raise UserError(_("Please upload a CRM CSV file."))
                csv_path = self._save_uploaded_file(self.crm_file, self.crm_filename)
                temp_file = csv_path

            preview_lines = []
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader):
                    if i >= 10:
                        break
                    company = row.get("Company", "")
                    first = row.get("First Name", "")
                    last = row.get("Last Name", "")
                    status = row.get("Lead Status", "")
                    role = row.get("Buyer/Supplier", "")
                    preview_lines.append(f"{i + 1}. {company} | {first} {last} | {status} | {role}")

            total = self._count_csv_rows(csv_path)
            self.total_rows = total

            self.result_message = f"CSV Preview (first 10 of {total} rows):\n{'=' * 50}\n" + "\n".join(preview_lines)

        finally:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return self._return_wizard()
