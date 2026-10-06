"""Deal realization for the ERP historical import.

Extends ``plasticos.erp.import`` after that model has loaded the canonical ERP
source package and written partner stages. This module owns deal headers, deal
lines, and per-deal atomicity. It does not read the source a second way and it
does not copy the partner mapping tables.

One BuySellNo is one logical unit. Header, every line, and every identity
marker are written inside a single savepoint, so a failing line leaves no
partial deal and no stale marker.
"""

from __future__ import annotations

import logging

from odoo import models

_logger = logging.getLogger(__name__)

PLASTICOS_TRANSACTION = "plasticos.transaction"
PLASTICOS_TRANSACTION_LINE = "plasticos.transaction.line"


class PlasticosLegacyErpImport(models.AbstractModel):
    """Historical deal rows for an ERP import that already wrote partners."""

    _inherit = "plasticos.erp.import"

    def _extend_historical_import(self, index, report, partner_by_cp, limit, commit, dry_run) -> bool:
        """Realize deal headers and lines from the source index already built."""
        from odoo.addons.plasticos_partner_import.erp import header_forensics

        headers = header_forensics.reconstruct_all_headers(index)
        self._import_transactions(index, headers, report, partner_by_cp, limit, commit, dry_run)
        return True

    def _import_transactions(self, index, headers, report, partner_by_cp, limit, commit, dry_run) -> None:
        buysell_numbers = index.buysell_numbers()
        if limit:
            buysell_numbers = buysell_numbers[:limit]

        for buysell_no in buysell_numbers:
            header = headers[buysell_no]
            for anomaly in header.anomalies:
                report.anomaly("Transaction", buysell_no, anomaly)

            if dry_run:
                report.skip("transactions")
                report.bump("transaction_lines", "skipped", len(header.detail_ids))
                continue

            try:
                # One BuySellNo = one logical unit. Header, all lines, and all
                # identity markers commit together or not at all.
                with self.env.cr.savepoint():
                    self._import_one_transaction(index, header, report, partner_by_cp)
            except Exception as exc:  # noqa: BLE001 - one bad unit must not abort the run
                report.error(buysell_no, str(exc))
                _logger.exception("ERP transaction %s failed and was rolled back", buysell_no)
                continue

            if commit:
                # Only ever between complete transactions.
                self.env.cr.commit()

    def _import_one_transaction(self, index, header, report, partner_by_cp) -> None:
        from odoo.addons.plasticos_partner_import.models.erp_import_service import IMPORT_CONTEXT

        Transaction = self.env[PLASTICOS_TRANSACTION].with_context(**IMPORT_CONTEXT)

        values = {"name": header.buysell_no, "state": header.state}
        supplier_id = partner_by_cp.get(header.supplier_cp_id) if header.supplier_cp_id else None
        buyer_id = partner_by_cp.get(header.buyer_cp_id) if header.buyer_cp_id else None
        if supplier_id:
            values["supplier_id"] = supplier_id
        if buyer_id:
            values["buyer_id"] = buyer_id

        # The reconstructed trade date is written only where a semantically
        # correct field exists. No field is invented for it; see
        # docs/erp_import_mapping.md, "Evidenced new-field candidate".
        if header.trade_date and "transaction_date" in Transaction._fields:
            values["transaction_date"] = header.trade_date

        transaction = self._upsert(
            Transaction, f"legacy_erp_transaction_{header.buysell_no}", values, report, "transactions"
        )
        self._import_lines(index, header, transaction, report)

    def _import_lines(self, index, header, transaction, report) -> None:
        from odoo.addons.plasticos_partner_import.erp import mapping
        from odoo.addons.plasticos_partner_import.models.erp_import_service import IMPORT_CONTEXT, _set_if, _text

        Line = self.env[PLASTICOS_TRANSACTION_LINE].with_context(**IMPORT_CONTEXT)

        for detail_id in header.detail_ids:
            row = index.lines[detail_id]
            values = {
                "transaction_id": transaction.id,
                "detail_id": detail_id,
                "units": mapping.parse_decimal(row.get("Units")) or 1.0,
            }
            _set_if(values, "grade_id", _text(row, "GradeID"))
            _set_if(values, "description", _text(row, "InvoiceDesc"))
            _set_if(values, "lot_no", _text(row, "LotNo"))
            _set_if(values, "color", _text(row, "Color"))
            _set_if(values, "sale_po", _text(row, "SPo"))
            _set_if(values, "purchase_po", _text(row, "PPo"))
            _set_if(values, "specifications", _text(row, "Comment"))

            for target, column in (
                ("sale_weight", "SWeight"),
                ("purchase_weight", "PWeight"),
                ("sale_price", "SPrice"),
                ("purchase_price", "PPrice"),
                ("sale_amount", "SAmount"),
                ("purchase_amount", "PAmount"),
            ):
                parsed = mapping.parse_decimal(row.get(column))
                if parsed is None and _text(row, column):
                    report.anomaly("WKSDetail", detail_id, f"unparsable {column}={row.get(column)!r}")
                elif parsed is not None:
                    values[target] = parsed

            uom, uom_anomaly = mapping.weight_uom(row.get("SWeightUOM"), row.get("PWeightUOM"))
            if uom:
                values["weight_uom"] = uom
            elif uom_anomaly:
                report.anomaly("WKSDetail", detail_id, uom_anomaly)

            unit, unit_anomaly = mapping.unit_type(row.get("UnitType"))
            if unit:
                values["unit_type"] = unit
            elif unit_anomaly:
                report.anomaly("WKSDetail", detail_id, unit_anomaly)

            self._upsert(Line, f"legacy_erp_detail_{detail_id}", values, report, "transaction_lines")
