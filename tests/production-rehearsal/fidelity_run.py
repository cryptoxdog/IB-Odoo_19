"""Read the rehearsal clone and the restored SQL Server source, then compare them.

The SQL text here is the checker's own read. It does not call the importer.
A missing extract is written as incomplete evidence, which fails Gate 6.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from fidelity import evaluate, finish

# Marker ``fidelity_odoo`` lets the kit fixture return a snapshot without Postgres.
ODOO_EXTRACT_SQL = """
-- fidelity_odoo
SELECT json_build_object(
  'evidence', 'complete',
  'partners', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name,
      'partner_id', p.id,
      'name', p.name,
      'ref', p.ref,
      'email', p.email,
      'website', p.website,
      'active', p.active,
      'supplier_rank', p.supplier_rank,
      'customer_rank', p.customer_rank,
      'company_role', to_jsonb(p)->>'company_role',
      'credit_limit', to_jsonb(p)->>'credit_limit',
      'street', p.street,
      'street2', p.street2,
      'city', p.city,
      'zip', p.zip,
      'is_company', p.is_company,
      'parent_id', p.parent_id
    ))
    FROM ir_model_data d
    JOIN res_partner p ON p.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'res.partner'
      AND d.name LIKE 'legacy_erp_%'
  ), '[]'::json),
  'sale_orders', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'name', so.name, 'origin', so.origin,
      'date_order', so.date_order, 'client_order_ref', so.client_order_ref,
      'state', so.state,
      'incoterm_code', (
        SELECT ic.code FROM account_incoterms ic
        WHERE ic.id = NULLIF(to_jsonb(so)->>'incoterm', '')::int
      )
    ))
    FROM ir_model_data d
    JOIN sale_order so ON so.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'sale.order'
      AND d.name LIKE 'legacy_erp_so_%'
  ), '[]'::json),
  'purchase_orders', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'name', po.name, 'origin', po.origin,
      'date_order', po.date_order, 'date_approve', po.date_approve, 'state', po.state,
      'incoterm_code', (
        SELECT ic.code FROM account_incoterms ic
        WHERE ic.id = NULLIF(to_jsonb(po)->>'incoterm_id', '')::int
      )
    ))
    FROM ir_model_data d
    JOIN purchase_order po ON po.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'purchase.order'
      AND d.name LIKE 'legacy_erp_po_%'
  ), '[]'::json),
  'sale_lines', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'qty', l.product_uom_qty, 'price', l.price_unit, 'name', l.name,
      'uom_xml', (
        SELECT u.module || '.' || u.name FROM ir_model_data u
        WHERE u.model = 'uom.uom' AND u.res_id = l.product_uom_id LIMIT 1
      )
    ))
    FROM ir_model_data d
    JOIN sale_order_line l ON l.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'sale.order.line'
      AND d.name LIKE 'legacy_erp_sol_%'
  ), '[]'::json),
  'purchase_lines', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'qty', l.product_qty, 'price', l.price_unit, 'name', l.name,
      'date_planned', l.date_planned, 'order_date', po.date_order,
      'uom_xml', (
        SELECT u.module || '.' || u.name FROM ir_model_data u
        WHERE u.model = 'uom.uom' AND u.res_id = l.product_uom_id LIMIT 1
      )
    ))
    FROM ir_model_data d
    JOIN purchase_order_line l ON l.id = d.res_id
    JOIN purchase_order po ON po.id = l.order_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'purchase.order.line'
      AND d.name LIKE 'legacy_erp_pol_%'
  ), '[]'::json),
  'invoices', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'move_type', m.move_type, 'invoice_date', m.invoice_date,
      'invoice_origin', m.invoice_origin, 'ref', m.ref, 'amount_total', m.amount_total,
      'state', m.state
    ))
    FROM ir_model_data d
    JOIN account_move m ON m.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'account.move'
      AND d.name LIKE 'legacy_erp_outinv_%'
  ), '[]'::json),
  'bills', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'move_type', m.move_type, 'invoice_date', m.invoice_date,
      'invoice_origin', m.invoice_origin, 'ref', m.ref, 'amount_total', m.amount_total,
      'state', m.state
    ))
    FROM ir_model_data d
    JOIN account_move m ON m.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'account.move'
      AND d.name LIKE 'legacy_erp_ininv_%'
  ), '[]'::json),
  'ledger_moves', COALESCE((
    SELECT json_agg(json_build_object(
      'xmlid', d.name, 'move_type', m.move_type, 'invoice_date', m.invoice_date,
      'invoice_origin', m.invoice_origin, 'ref', m.ref, 'amount_total', m.amount_total,
      'state', m.state
    ))
    FROM ir_model_data d
    JOIN account_move m ON m.id = d.res_id
    WHERE d.module = 'plasticos_transaction' AND d.model = 'account.move'
      AND d.name LIKE 'legacy_erp_ledger_%'
  ), '[]'::json)
);
"""


def _redact(message: str) -> str:
    text = message
    for name in ("ERP_SQL_PASSWORD", "ERP_SQL_DATABASE"):
        secret = os.environ.get(name) or ""
        if secret:
            text = text.replace(secret, "[redacted]")
    return text[:400]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value).strip()


def _rows(cursor, sql: str, keys: list[str]) -> list[dict]:
    """Run one static statement. Identifiers are bound parameters, in batches of 400."""
    found: list[dict] = []
    unique = list(dict.fromkeys(key for key in keys if key))
    for start in range(0, len(unique), 400):
        chunk = unique[start : start + 400]
        cursor.execute(sql.format(",".join(["%s"] * len(chunk))), tuple(chunk))  # noqa: S608
        found.extend(cursor.fetchall())
    return [{key: _cell(row[key]) for key in row} for row in found]


def _worksheets(odoo: dict) -> list[str]:
    numbers: list[str] = []
    for kind in ("sale_orders", "purchase_orders"):
        for order in odoo.get(kind) or []:
            numbers.extend(part.strip() for part in str(order.get("origin") or "").split(",") if part.strip())
    for kind in ("invoices", "bills", "ledger_moves"):
        for move in odoo.get(kind) or []:
            origin = str(move.get("invoice_origin") or "").strip()
            if origin:
                numbers.append(origin)
    return numbers


def _suffixes(rows: list, prefix: str) -> list[str]:
    return [
        str(row.get("xmlid") or "").removeprefix(prefix)
        for row in rows
        if str(row.get("xmlid") or "").startswith(prefix)
    ]


def _sale_headers(cursor, bundle: dict) -> None:
    line_keys = [
        str(row.get("SPO_ID") or "").strip()
        for row in bundle["details"].values()
        if str(row.get("SPO_ID") or "").strip()
    ]
    for row in _rows(
        cursor,
        """
        SELECT CONVERT(varchar(40), PO_ID) AS PO_ID, RTRIM(PONumber) AS PONumber
        FROM dbo.PODetail WHERE CONVERT(varchar(40), PO_ID) IN ({})
        """,
        line_keys,
    ):
        bundle["order_lines"][row["PO_ID"]] = row["PONumber"]
    for row in _rows(
        cursor,
        """
        SELECT RTRIM(PONumber) AS PONumber, CONVERT(varchar(20), COUNT(*)) AS HeaderCount
        FROM dbo.PO WHERE RTRIM(Source) = 'SO' AND RTRIM(PONumber) IN ({})
        GROUP BY RTRIM(PONumber)
        """,
        list(bundle["order_lines"].values()),
    ):
        bundle["sale_header_count"][row["PONumber"]] = row["HeaderCount"]


def read_source(odoo: dict) -> dict:
    """Source rows for the identities the clone actually imported."""
    try:
        import pymssql
    except ImportError as exc:
        return {"evidence": "missing", "missing_reason": f"SQL reader is not available ({exc.__class__.__name__})"}
    server = os.environ.get("ERP_SQL_SERVER") or ""
    database = os.environ.get("ERP_SQL_DATABASE") or ""
    password = os.environ.get("ERP_SQL_PASSWORD") or ""
    if not server or not database or not password:
        return {"evidence": "missing", "missing_reason": "ERP SQL coordinates are incomplete"}
    if server == "host.docker.internal" and os.environ.get("FIDELITY_IN_WEB") != "1":
        server = "127.0.0.1"
    try:
        connection = pymssql.connect(
            server=server,
            port=int(os.environ.get("ERP_SQL_PORT") or "1433"),
            user=os.environ.get("ERP_SQL_USER") or "erp_reader",
            password=password,
            database=database,
            login_timeout=20,
            timeout=180,
        )
    except Exception as exc:
        return {"evidence": "missing", "missing_reason": f"SQL source unreadable ({_redact(str(exc))})"}
    try:
        cursor = connection.cursor(as_dict=True)
        companies = _suffixes(odoo.get("partners") or [], "legacy_erp_cp_")
        contacts = [
            item
            for item in _suffixes(odoo.get("partners") or [], "legacy_erp_contact_")
            if not item.startswith("role_")
        ]
        orders = [
            str(row.get("name") or "") for row in (odoo.get("sale_orders") or []) + (odoo.get("purchase_orders") or [])
        ]
        worksheets = _worksheets(odoo)
        payables = _suffixes(odoo.get("bills") or [], "legacy_erp_ininv_")
        ledgers = _suffixes(odoo.get("ledger_moves") or [], "legacy_erp_ledger_")
        bundle = {
            "evidence": "complete",
            "counterparties": {},
            "addresses": {},
            "contacts": {},
            "details": {},
            "details_by_token": {},
            "order_lines": {},
            "sale_header_count": {},
            "orders": {},
            "buysell": {},
            "ledger": {},
            "ledger_rows": {},
            "payables_by_token": {},
            "batches": {},
        }
        if companies:
            for row in _rows(
                cursor,
                """
                SELECT RTRIM(CpID) AS CpID, CompanyNm, Role, ActiveStatus, OurCustNo, APEMail, WebSite,
                       CONVERT(varchar(40), CreditLimit) AS CreditLimit
                FROM dbo.CounterParty WHERE RTRIM(CpID) IN ({})
                """,
                companies,
            ):
                bundle["counterparties"][row["CpID"]] = row
            for row in _rows(
                cursor,
                """
                SELECT CONVERT(varchar(40), AddressID) AS AddressID, RTRIM(CpID) AS CpID, RTRIM(Type) AS Type,
                       Addr1, Addr2, Addr3, City, PostalCd, InvoiceAddr, RemitToAddress,
                       CONVERT(varchar(20), isBillingAddressOnly) AS isBillingAddressOnly
                FROM dbo.Address WHERE RTRIM(CpID) IN ({})
                """,
                companies,
            ):
                bundle["addresses"][row["AddressID"]] = row
        if contacts:
            for row in _rows(
                cursor,
                """
                SELECT CONVERT(varchar(40), CT_ID) AS CT_ID, RTRIM(CpID) AS CpID, ContactNm, Email,
                       RTRIM(IsActive) AS IsActive
                FROM dbo.Contact WHERE CONVERT(varchar(40), CT_ID) IN ({})
                """,
                contacts,
            ):
                bundle["contacts"][row["CT_ID"]] = row
        if orders:
            for row in _rows(
                cursor,
                """
                SELECT RTRIM(PONumber) AS PONumber, CONVERT(varchar(19), PODate, 120) AS PODate,
                       RTRIM(Source) AS Source, RTRIM(PriceBasis) AS PriceBasis, RTRIM(POReference) AS POReference
                FROM dbo.PO WHERE RTRIM(PONumber) IN ({})
                """,
                orders,
            ):
                bundle["orders"][f"{row['PONumber']}|{row['Source']}"] = row
        if worksheets:
            for row in _rows(
                cursor,
                """
                SELECT CONVERT(varchar(40), DetailID) AS DetailID, RTRIM(BuySellNo) AS BuySellNo, InvoiceDesc,
                       RTRIM(SPO_ID) AS SPO_ID,
                       CONVERT(varchar(40), SWeight) AS SWeight, RTRIM(SWeightUOM) AS SWeightUOM,
                       CONVERT(varchar(40), SPrice) AS SPrice, CONVERT(varchar(40), SAmount) AS SAmount,
                       CONVERT(varchar(40), PWeight) AS PWeight, RTRIM(PWeightUOM) AS PWeightUOM,
                       CONVERT(varchar(40), PPrice) AS PPrice, CONVERT(varchar(40), PAmount) AS PAmount
                FROM dbo.WKSDetail WHERE RTRIM(BuySellNo) IN ({})
                """,
                worksheets,
            ):
                bundle["details"][row["DetailID"]] = row
            _sale_headers(cursor, bundle)
            for row in _rows(
                cursor,
                """
                SELECT RTRIM(BuySellNo) AS BuySellNo, CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt,
                       CONVERT(varchar(19), OrderDt, 120) AS OrderDt, RTRIM(PriceBasis) AS PriceBasis
                FROM dbo.BuySell WHERE RTRIM(BuySellNo) IN ({})
                """,
                worksheets,
            ):
                bundle["buysell"][row["BuySellNo"]] = row
            for row in _rows(
                cursor,
                """
                SELECT CONVERT(varchar(40), LedgerID) AS LedgerID, CONVERT(varchar(19), TradeDt, 120) AS TradeDt,
                       RTRIM(BuySellNo) AS BuySellNo, RTRIM(Source) AS Source, CONVERT(varchar(40), Sale) AS Sale,
                       RTRIM(AdjType) AS AdjType, RTRIM(AdjApproved) AS AdjApproved, RTRIM(AdjMemoNo) AS AdjMemoNo
                FROM dbo.GPLedger WHERE RTRIM(BuySellNo) IN ({})
                """,
                worksheets,
            ):
                bundle["ledger"].setdefault(row["BuySellNo"], []).append(row["TradeDt"])
                bundle["ledger_rows"][row["LedgerID"]] = row
        if payables:
            for row in _rows(
                cursor,
                """
                SELECT RTRIM(PayableID) AS PayableID, RTRIM(BuySellNo) AS BuySellNo, RTRIM(GLAcct) AS GLAcct,
                       CONVERT(varchar(40), Amount) AS Amount, InvoiceNo,
                       CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt, RTRIM(APBatchNo) AS APBatchNo
                FROM dbo.Payables WHERE RTRIM(PayableID) IN ({})
                """,
                payables,
            ):
                bundle["payables_by_token"][row["PayableID"]] = row
            batches = [row["APBatchNo"] for row in bundle["payables_by_token"].values() if row.get("APBatchNo")]
            for row in _rows(
                cursor,
                """
                SELECT RTRIM(APBatchNo) AS APBatchNo, InvoiceNo, CONVERT(varchar(19), InvoiceDt, 120) AS InvoiceDt
                FROM dbo.PayablesBatch WHERE RTRIM(APBatchNo) IN ({})
                """,
                batches,
            ):
                bundle["batches"][row["APBatchNo"]] = row
        if ledgers:
            for row in _rows(
                cursor,
                """
                SELECT CONVERT(varchar(40), LedgerID) AS LedgerID, CONVERT(varchar(19), TradeDt, 120) AS TradeDt,
                       RTRIM(BuySellNo) AS BuySellNo, RTRIM(Source) AS Source, CONVERT(varchar(40), Sale) AS Sale,
                       RTRIM(AdjType) AS AdjType, RTRIM(AdjApproved) AS AdjApproved, RTRIM(AdjMemoNo) AS AdjMemoNo
                FROM dbo.GPLedger WHERE CONVERT(varchar(40), LedgerID) IN ({})
                """,
                ledgers,
            ):
                bundle["ledger_rows"][row["LedgerID"]] = row
    except Exception as exc:
        return {"evidence": "missing", "missing_reason": f"SQL extract failed ({_redact(str(exc))})"}
    finally:
        connection.close()
    from fidelity import source_token

    indexed: dict[str, dict] = {}
    for detail in bundle["details"].values():
        token = source_token(detail.get("DetailID"))
        if token in indexed and indexed[token].get("DetailID") != detail.get("DetailID"):
            indexed[token] = {"_ambiguous": True, "DetailID": token}
        else:
            indexed[token] = detail
    bundle["details_by_token"] = indexed
    return bundle


def _stub_source() -> dict | None:
    stub_dir = os.environ.get("STUB_DIR")
    source = os.environ.get("REHEARSAL_FIDELITY_SOURCE")
    if not stub_dir or not source:
        return None
    root = Path(stub_dir).resolve()
    path = Path(source).resolve()
    if path != root and root not in path.parents:
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {"evidence": "missing", "missing_reason": "fixture source is not an object"}
    return loaded


def _unresolved(path: str | None) -> list:
    if not path:
        return []
    file = Path(path)
    if not file.is_file():
        return []
    try:
        loaded = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = loaded.get("unresolved") if isinstance(loaded, dict) else None
    return rows if isinstance(rows, list) else []


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    path.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--print-odoo-sql", action="store_true")
    parser.add_argument("--odoo")
    parser.add_argument("--out")
    parser.add_argument("--coverage")
    parser.add_argument("--census")
    args = parser.parse_args(argv)
    if args.print_odoo_sql:
        sys.stdout.write(ODOO_EXTRACT_SQL)
        return 0
    if not args.odoo or not args.out:
        parser.error("--odoo and --out are required")
    out = Path(args.out)
    odoo_path = Path(args.odoo)
    if not odoo_path.is_file():
        report = finish([], "missing", "the clone snapshot was not read")
    else:
        try:
            odoo = json.loads(odoo_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            odoo = {"evidence": "missing", "missing_reason": f"clone snapshot unreadable ({exc.__class__.__name__})"}
        if not isinstance(odoo, dict):
            odoo = {"evidence": "missing", "missing_reason": "clone snapshot is not an object"}
        source = _stub_source() if os.environ.get("STUB_DIR") else None
        if source is None:
            source = read_source(odoo if odoo.get("evidence") == "complete" else {})
        report = evaluate(odoo, source, _unresolved(args.census), retain_passes=False)
    _write(out, report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
