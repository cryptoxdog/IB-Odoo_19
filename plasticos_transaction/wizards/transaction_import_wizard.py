"""
Transaction Import Wizard
Import transactions from ERP WksDetail CSV export.
"""

import base64
import csv
import io
import logging
from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Default CSV file in module
DEFAULT_CSV = "ERP.WksDetail.Test.csv"


class TransactionImportWizard(models.TransientModel):
    _name = "plasticos.transaction.import.wizard"
    _description = "Transaction Import Wizard"

    csv_file = fields.Binary(
        string="CSV File",
        help="Upload ERP WksDetail CSV file. Leave empty to use default file in module.",
    )
    csv_filename = fields.Char(string="Filename")

    use_default_file = fields.Boolean(
        string="Use Default CSV File",
        default=True,
        help="Use the ERP.WksDetail.csv file included in the module.",
    )

    dry_run = fields.Boolean(
        string="Dry Run",
        default=True,
        help="Preview import without creating records.",
    )

    skip_existing = fields.Boolean(
        string="Skip Existing Transactions",
        default=True,
        help="Skip transactions that already exist (by BuySellNo reference).",
    )

    result_message = fields.Text(
        string="Result",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Configure"),
            ("preview", "Preview"),
            ("done", "Complete"),
        ],
        default="draft",
    )

    # Preview stats
    preview_tx_count = fields.Integer(string="Transactions to Import", readonly=True)
    preview_line_count = fields.Integer(string="Line Items to Import", readonly=True)
    preview_skip_count = fields.Integer(string="Transactions to Skip (existing)", readonly=True)

    def _get_module_path(self):
        """Get the path to the plasticos_transaction module."""
        import odoo.modules.module as mod

        path = mod.get_module_path("plasticos_transaction")
        if not path:
            raise UserError(_("Could not determine module path."))
        return path

    def _get_csv_reader(self):
        """Get CSV reader from uploaded file or default file."""
        import os

        if self.use_default_file:
            module_path = self._get_module_path()
            csv_path = os.path.join(module_path, os.pardir, DEFAULT_CSV)
            if not os.path.exists(csv_path):
                raise UserError(_("Default CSV file not found: %s") % csv_path)
            with open(csv_path, encoding="utf-8-sig") as f:
                content = f.read()
        else:
            if not self.csv_file:
                raise UserError(_("Please upload a CSV file."))
            content = base64.b64decode(self.csv_file).decode("utf-8-sig")

        return csv.DictReader(io.StringIO(content))

    def _parse_float(self, value):
        """Parse float from CSV value, handling NULL and empty strings."""
        if not value or value.strip() in ("NULL", "", "0"):
            return 0.0
        try:
            return float(value.strip())
        except (ValueError, TypeError):
            return 0.0

    def _parse_string(self, value):
        """Parse string from CSV value, handling NULL and whitespace."""
        if not value or value.strip() in ("NULL", "(none)"):
            return False
        return value.strip()

    def _group_lines_by_transaction(self, reader):
        """Group CSV rows by BuySellNo (transaction reference)."""
        transactions = defaultdict(list)
        for row in reader:
            buy_sell_no = self._parse_string(row.get("BuySellNo", ""))
            if buy_sell_no:
                transactions[buy_sell_no].append(row)
        return transactions

    def action_preview(self):
        """Preview the import without creating records."""
        self.ensure_one()

        reader = self._get_csv_reader()
        transactions = self._group_lines_by_transaction(reader)

        # Check for existing transactions
        existing_refs = set(
            self.env["plasticos.transaction"].search([("name", "in", list(transactions.keys()))]).mapped("name")
        )

        new_tx_count = 0
        skip_count = 0
        total_lines = 0

        for ref, lines in transactions.items():
            if ref in existing_refs:
                skip_count += 1
            else:
                new_tx_count += 1
                total_lines += len(lines)

        self.preview_tx_count = new_tx_count
        self.preview_line_count = total_lines
        self.preview_skip_count = skip_count
        self.state = "preview"

        preview_msg = [
            _("CSV File Analysis Complete"),
            "",
            _("Total unique transactions in CSV: %d") % len(transactions),
            _("New transactions to import: %d") % new_tx_count,
            _("Line items to import: %d") % total_lines,
        ]
        if skip_count:
            preview_msg.append(_("Existing transactions to skip: %d") % skip_count)

        # Show sample transaction references
        sample_refs = list(transactions.keys())[:10]
        preview_msg.append("")
        preview_msg.append(_("Sample transaction references:"))
        for ref in sample_refs:
            status = "(exists)" if ref in existing_refs else "(new)"
            preview_msg.append(f"  - {ref} {status}")
        if len(transactions) > 10:
            preview_msg.append(f"  ... and {len(transactions) - 10} more")

        self.result_message = "\n".join(preview_msg)
        return self._return_wizard()

    def action_import(self):
        """Execute the import."""
        self.ensure_one()

        # If dry_run is checked and not forcing, just preview
        if self.dry_run and not self.env.context.get("force_import"):
            return self.action_preview()

        reader = self._get_csv_reader()
        transactions = self._group_lines_by_transaction(reader)

        # Check for existing transactions
        existing_refs = set()
        if self.skip_existing:
            existing_refs = set(
                self.env["plasticos.transaction"].search([("name", "in", list(transactions.keys()))]).mapped("name")
            )

        Transaction = self.env["plasticos.transaction"]
        TransactionLine = self.env["plasticos.transaction.line"]

        created_tx = 0
        created_lines = 0
        skipped_tx = 0
        errors = []

        for ref, lines in transactions.items():
            if ref in existing_refs:
                skipped_tx += 1
                continue

            try:
                # Aggregate transaction-level data from lines
                total_sale = sum(self._parse_float(l.get("SAmount", 0)) for l in lines)
                total_purchase = sum(self._parse_float(l.get("PAmount", 0)) for l in lines)
                total_weight = sum(self._parse_float(l.get("SWeight", 0)) for l in lines)

                # Create transaction
                tx_vals = {
                    "name": ref,
                    "state": "closed",  # Historical data
                    "historical_sale_total": total_sale,
                    "historical_purchase_total": total_purchase,
                    "expected_weight": total_weight,
                    "actual_weight": total_weight,
                }

                tx = Transaction.create(tx_vals)
                created_tx += 1

                # Create line items
                for line_data in lines:
                    line_vals = {
                        "transaction_id": tx.id,
                        "detail_id": self._parse_string(line_data.get("DetailID", "")),
                        "grade_id": self._parse_string(line_data.get("GradeID", "")),
                        "description": self._parse_string(line_data.get("InvoiceDesc", "")),
                        "sale_weight": self._parse_float(line_data.get("SWeight", 0)),
                        "sale_price": self._parse_float(line_data.get("SPrice", 0)),
                        "sale_amount": self._parse_float(line_data.get("SAmount", 0)),
                        "purchase_weight": self._parse_float(line_data.get("PWeight", 0)),
                        "purchase_price": self._parse_float(line_data.get("PPrice", 0)),
                        "purchase_amount": self._parse_float(line_data.get("PAmount", 0)),
                        "color": self._parse_string(line_data.get("Color", "")),
                        "container_no": self._parse_string(line_data.get("ContainerNo", "")),
                        "seal_no": self._parse_string(line_data.get("SealNo", "")),
                        "sale_po": self._parse_string(line_data.get("SPo", "")),
                        "purchase_po": self._parse_string(line_data.get("PPo", "")),
                        "specifications": self._parse_string(line_data.get("Specifications", "")),
                        "condition": self._parse_string(line_data.get("Condition", "")),
                        "unit_type": self._parse_string(line_data.get("UnitType", "")),
                        "units": self._parse_float(line_data.get("Units", 0)),
                    }
                    TransactionLine.create(line_vals)
                    created_lines += 1

            except Exception as e:
                errors.append(f"{ref}: {str(e)}")
                _logger.exception("Error importing transaction %s", ref)

        # Build result message
        result_parts = [
            _("Import Complete!"),
            "",
            _("Transactions created: %d") % created_tx,
            _("Line items created: %d") % created_lines,
        ]
        if skipped_tx:
            result_parts.append(_("Transactions skipped (existing): %d") % skipped_tx)
        if errors:
            result_parts.append("")
            result_parts.append(_("Errors (%d):") % len(errors))
            for err in errors[:10]:
                result_parts.append(f"  - {err}")
            if len(errors) > 10:
                result_parts.append(f"  ... and {len(errors) - 10} more")

        self.result_message = "\n".join(result_parts)
        self.state = "done"
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

    def action_back(self):
        """Go back to configuration."""
        self.state = "draft"
        self.result_message = False
        return self._return_wizard()

    def action_close(self):
        """Close the wizard."""
        return {"type": "ir.actions.act_window_close"}

    def action_view_transactions(self):
        """Open the transactions list view."""
        return {
            "type": "ir.actions.act_window",
            "name": _("Imported Transactions"),
            "res_model": "plasticos.transaction",
            "view_mode": "list,form",
            "domain": [("state", "=", "closed")],
            "context": {"search_default_filter_closed": 1},
        }
