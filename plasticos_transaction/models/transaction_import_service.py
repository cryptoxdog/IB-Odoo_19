"""
Transaction Import Service for seeding historical cieTrade data.

Imports transaction line details from cieTrade.WksDetail.csv into:
- plasticos.transaction (header records, grouped by BuySellNo)
- plasticos.transaction.line (detail records)

Usage (shell):
    env["plasticos.transaction.import.service"].run_csv_import(
        "/path/to/cieTrade.WksDetail.csv"
    )

REVIEWER NOTE: This service intentionally calls self.env.cr.commit() every
BATCH_SIZE records. This breaks Odoo's transactional guarantees but is
acceptable here because:
1. This is a one-time historical import service (AbstractModel, no UI wizard)
2. Large imports (10k+ records) would otherwise timeout or OOM
3. The external ID check makes it idempotent — re-running skips existing records
Do NOT expose this as a UI wizard without removing the mid-transaction commits.
"""

import csv
import logging
import re
from collections import defaultdict

from odoo import api, models

_logger = logging.getLogger(__name__)

BATCH_SIZE = 100

# Valid weight UOM codes
VALID_WEIGHT_UOMS = {"L", "S", "E"}

# Valid unit type codes (map legacy "9" to "O" for Other)
VALID_UNIT_TYPES = {"B", "G", "X", "P", "L", "A", "F", "H", "C", "E", "O"}
UNIT_TYPE_MAP = {"9": "O"}  # Legacy code mapping


class PlasticosTransactionImportService(models.AbstractModel):
    _name = "plasticos.transaction.import.service"
    _description = "Transaction CSV Import Service"

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @api.model
    def run_csv_import(self, csv_path: str, dry_run: bool = False) -> dict:
        """
        Import historical transactions from cieTrade.WksDetail.csv.

        Args:
            csv_path: Absolute path to the CSV file
            dry_run: If True, validate but don't commit

        Returns:
            dict with counts: transactions_created, lines_created, errors
        """
        _logger.info("Starting transaction import from %s (dry_run=%s)", csv_path, dry_run)

        rows = self._read_csv(csv_path)
        if not rows:
            return {"transactions_created": 0, "lines_created": 0, "errors": ["No rows found"]}

        # Group rows by BuySellNo (transaction reference)
        grouped = self._group_by_transaction(rows)
        _logger.info("Found %d unique transactions from %d line items", len(grouped), len(rows))

        tx_created = 0
        lines_created = 0
        errors = []

        for i, (buysell_no, line_rows) in enumerate(grouped.items()):
            try:
                tx, line_count = self._import_transaction(buysell_no, line_rows, dry_run)
                if tx:
                    tx_created += 1
                    lines_created += line_count

                if (i + 1) % BATCH_SIZE == 0:
                    if not dry_run:
                        self.env.cr.commit()
                    _logger.info("Progress: %d/%d transactions", i + 1, len(grouped))

            except Exception as e:
                errors.append(f"BuySellNo {buysell_no}: {str(e)}")
                _logger.error("Error importing %s: %s", buysell_no, e)

        if not dry_run:
            self.env.cr.commit()

        result = {
            "transactions_created": tx_created,
            "lines_created": lines_created,
            "errors": errors,
        }
        _logger.info("Import complete: %s", result)
        return result

    # -------------------------------------------------------------------------
    # CSV Parsing
    # -------------------------------------------------------------------------

    def _read_csv(self, csv_path: str) -> list:
        """Read CSV file and return list of row dicts."""
        try:
            with open(csv_path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            _logger.error("Failed to read CSV: %s", e)
            return []

    def _group_by_transaction(self, rows: list) -> dict:
        """Group CSV rows by BuySellNo (transaction reference)."""
        grouped = defaultdict(list)
        for row in rows:
            buysell_no = row.get("BuySellNo", "").strip()
            if buysell_no:
                grouped[buysell_no].append(row)
        return grouped

    # -------------------------------------------------------------------------
    # Transaction Import
    # -------------------------------------------------------------------------

    def _import_transaction(self, buysell_no: str, line_rows: list, dry_run: bool) -> tuple:
        """
        Import a single transaction with its lines.

        Returns:
            tuple: (transaction_record, line_count) or (None, 0) if skipped
        """
        # Check if transaction already exists (idempotent)
        ext_id = self._make_external_id("transaction", buysell_no)
        existing = self.env.ref(ext_id, raise_if_not_found=False)
        if existing:
            _logger.debug("Transaction %s already exists, skipping", buysell_no)
            return (None, 0)

        # Calculate transaction totals from lines
        totals = self._calculate_totals(line_rows)

        # Create transaction header
        tx_vals = {
            "name": buysell_no,
            "state": "closed",  # Historical data = already closed
            # Store computed totals as reference (actual compute will recalc)
            # These are informational since the model computes from linked invoices
        }

        if dry_run:
            _logger.debug("DRY RUN: Would create transaction %s", buysell_no)
            return (None, len(line_rows))

        # Create transaction
        tx = (
            self.env["plasticos.transaction"]
            .with_context(
                import_mode=True,  # Skip validation constraints during import
                tracking_disable=True,  # Skip mail tracking
            )
            .create(tx_vals)
        )

        # Register external ID
        self._create_external_id("plasticos.transaction", tx.id, ext_id)

        # Create transaction lines
        line_count = self._create_transaction_lines(tx, line_rows)

        _logger.debug("Created transaction %s with %d lines", buysell_no, line_count)
        return (tx, line_count)

    def _create_transaction_lines(self, tx, line_rows: list) -> int:
        """Create transaction line records."""
        Line = self.env["plasticos.transaction.line"]
        count = 0

        for row in line_rows:
            line_vals = self._parse_line_row(tx, row)
            if line_vals:
                Line.create(line_vals)
                count += 1

        return count

    def _parse_line_row(self, tx, row: dict) -> dict:
        """Parse a CSV row into transaction line values."""
        detail_id = row.get("DetailID", "").strip()
        grade_id = row.get("GradeID", "").strip()
        description = row.get("InvoiceDesc", "").strip()

        # Weights
        sale_weight = self._parse_float(row.get("SWeight", "0"))
        purchase_weight = self._parse_float(row.get("PWeight", "0"))
        weight_uom_raw = row.get("SWeightUOM", "L").strip()
        weight_uom = weight_uom_raw if weight_uom_raw in VALID_WEIGHT_UOMS else "L"

        # Prices and amounts
        sale_price = self._parse_float(row.get("SPrice", "0"))
        purchase_price = self._parse_float(row.get("PPrice", "0"))
        sale_amount = self._parse_float(row.get("SAmount", "0"))
        purchase_amount = self._parse_float(row.get("PAmount", "0"))

        # Additional fields
        specifications = row.get("Specifications", "").strip()
        lot_no = row.get("LotNo", "").strip()
        container_no = row.get("ContainerNo", "").strip()

        # Unit type (container/packaging type) - validate against selection
        unit_type_raw = row.get("UnitType", "").strip()
        # Map legacy codes (e.g., "9" -> "O")
        unit_type_raw = UNIT_TYPE_MAP.get(unit_type_raw, unit_type_raw)
        unit_type = unit_type_raw if unit_type_raw in VALID_UNIT_TYPES else False

        units = self._parse_float(row.get("Units", "1"))
        if units <= 0:
            units = 1.0

        condition = row.get("Condition", "").strip()
        color = row.get("Color", "").strip()

        # PO references
        sale_po = row.get("SPo", "").strip()
        purchase_po = row.get("PPo", "").strip()

        return {
            "transaction_id": tx.id,
            "detail_id": detail_id,
            "grade_id": grade_id,
            "description": description,
            "sale_weight": sale_weight,
            "purchase_weight": purchase_weight,
            "weight_uom": weight_uom,
            "sale_price": sale_price,
            "purchase_price": purchase_price,
            "sale_amount": sale_amount,
            "purchase_amount": purchase_amount,
            "specifications": specifications,
            "lot_no": lot_no,
            "container_no": container_no,
            "unit_type": unit_type,
            "units": units,
            "condition": condition,
            "color": color,
            "sale_po": sale_po,
            "purchase_po": purchase_po,
        }

    def _calculate_totals(self, line_rows: list) -> dict:
        """Calculate transaction totals from line items."""
        sale_total = sum(self._parse_float(r.get("SAmount", "0")) for r in line_rows)
        purchase_total = sum(self._parse_float(r.get("PAmount", "0")) for r in line_rows)
        weight_total = sum(self._parse_float(r.get("SWeight", "0")) for r in line_rows)

        return {
            "sale_total": sale_total,
            "purchase_total": purchase_total,
            "weight_total": weight_total,
            "margin": sale_total - purchase_total,
            "line_count": len(line_rows),
        }

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _parse_float(self, value: str) -> float:
        """Safely parse a float from string."""
        if not value:
            return 0.0
        try:
            cleaned = re.sub(r"[^\d.\-]", "", str(value).strip())
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _make_external_id(self, prefix: str, ref: str) -> str:
        """Generate external ID for idempotent upserts."""
        safe_ref = re.sub(r"[^a-zA-Z0-9_]", "_", ref)
        return f"plasticos_transaction.import_{prefix}_{safe_ref}"

    def _create_external_id(self, model: str, res_id: int, ext_id: str) -> None:
        """Create ir.model.data record for external ID."""
        module, name = ext_id.split(".", 1)
        self.env["ir.model.data"].create(
            {
                "module": module,
                "name": name,
                "model": model,
                "res_id": res_id,
                "noupdate": True,
            }
        )
