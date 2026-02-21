"""
Partner Import Wizard
Provides UI to trigger the partner import from CSV files.
"""

import logging
import os

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default paths relative to module directory
DEFAULT_CORPORATE_CSV = "1. Counterparties - Parent - CORPORATE-Ready To Import.csv"
DEFAULT_FACILITY_CSV = "2. Counterparties - Child - FACILITY LOCATIONS.csv"


class PartnerImportWizard(models.TransientModel):
    _name = "plasticos.partner.import.wizard"
    _description = "Partner Import Wizard"

    corporate_file = fields.Binary(
        string="Corporate CSV",
        help="CSV file with corporate/parent companies. Leave empty to use default file in module.",
    )
    corporate_filename = fields.Char(string="Corporate Filename")

    facility_file = fields.Binary(
        string="Facility CSV",
        help="CSV file with facilities and contacts. Leave empty to use default file in module.",
    )
    facility_filename = fields.Char(string="Facility Filename")

    use_default_files = fields.Boolean(
        string="Use Default CSV Files",
        default=True,
        help="Use the CSV files included in the plasticos_partner_import module.",
    )

    import_mode = fields.Selection(
        [
            ("full", "Full Import (Corporate + Facilities)"),
            ("corporate_only", "Corporate Only"),
            ("facility_only", "Facility Only"),
        ],
        string="Import Mode",
        default="full",
        required=True,
    )

    dry_run = fields.Boolean(
        string="Dry Run",
        default=False,
        help="Validate files without creating records.",
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

    def _get_module_path(self):
        """Get the path to the plasticos_partner_import module."""
        module = self.env["ir.module.module"].search([("name", "=", "plasticos_partner_import")], limit=1)
        if not module:
            raise UserError(_("Module plasticos_partner_import not found."))

        # Get module path from addons
        import odoo.modules.module as mod

        path = mod.get_module_path("plasticos_partner_import")
        if not path:
            raise UserError(_("Could not determine module path."))
        return path

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

    def action_import(self):
        """Run the partner import."""
        self.ensure_one()

        import_svc = self.env["plasticos.partner.import.service"]
        module_path = self._get_module_path()

        corporate_path = None
        facility_path = None
        temp_files = []

        try:
            # Determine file paths
            if self.use_default_files:
                if self.import_mode in ("full", "corporate_only"):
                    corporate_path = os.path.join(module_path, DEFAULT_CORPORATE_CSV)
                    if not os.path.exists(corporate_path):
                        raise UserError(_("Default corporate CSV not found: %s") % corporate_path)

                if self.import_mode in ("full", "facility_only"):
                    facility_path = os.path.join(module_path, DEFAULT_FACILITY_CSV)
                    if not os.path.exists(facility_path):
                        raise UserError(_("Default facility CSV not found: %s") % facility_path)
            else:
                # Use uploaded files
                if self.import_mode in ("full", "corporate_only"):
                    if not self.corporate_file:
                        raise UserError(_("Please upload a Corporate CSV file."))
                    corporate_path = self._save_uploaded_file(self.corporate_file, self.corporate_filename)
                    temp_files.append(corporate_path)

                if self.import_mode in ("full", "facility_only"):
                    if not self.facility_file:
                        raise UserError(_("Please upload a Facility CSV file."))
                    facility_path = self._save_uploaded_file(self.facility_file, self.facility_filename)
                    temp_files.append(facility_path)

            if self.dry_run:
                # Just validate
                messages = []
                if corporate_path:
                    messages.append(f"Corporate CSV validated: {corporate_path}")
                if facility_path:
                    messages.append(f"Facility CSV validated: {facility_path}")
                self.result_message = "\n".join(messages) + "\n\nDry run complete. No records created."
                self.state = "done"
                return self._return_wizard()

            # Run the actual import
            _logger.info(
                "Starting partner import: mode=%s, corporate=%s, facility=%s",
                self.import_mode,
                corporate_path,
                facility_path,
            )

            result = import_svc.run_csv_import(corporate_path, facility_path)

            # Format result message
            msg_parts = ["Import completed successfully!"]
            if result.get("corporates_created"):
                msg_parts.append(f"Corporate partners created: {result['corporates_created']}")
            if result.get("corporates_updated"):
                msg_parts.append(f"Corporate partners updated: {result['corporates_updated']}")
            if result.get("facilities_created"):
                msg_parts.append(f"Facilities created: {result['facilities_created']}")
            if result.get("facilities_updated"):
                msg_parts.append(f"Facilities updated: {result['facilities_updated']}")
            if result.get("contacts_created"):
                msg_parts.append(f"Contacts created: {result['contacts_created']}")
            if result.get("errors"):
                msg_parts.append(f"\nErrors: {len(result['errors'])}")
                for err in result["errors"][:10]:
                    msg_parts.append(f"  - {err}")
                if len(result["errors"]) > 10:
                    msg_parts.append(f"  ... and {len(result['errors']) - 10} more")

            self.result_message = "\n".join(msg_parts)
            self.state = "done"

        finally:
            # Clean up temp files
            for path in temp_files:
                if path and os.path.exists(path):
                    os.unlink(path)

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

    def action_view_partners(self):
        """Open the partners list view."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Imported Partners"),
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("is_company", "=", True)],
            "context": {"search_default_filter_companies": 1},
        }
