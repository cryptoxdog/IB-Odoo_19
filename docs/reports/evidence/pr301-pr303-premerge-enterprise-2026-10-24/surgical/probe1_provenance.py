"""#301 head only. One imported worksheet versus a normal invoice. Rolls back."""

import json

from odoo.addons.plasticos_partner_import.erp.report import ImportReport
from odoo.addons.plasticos_partner_import.erp.source_index import SourceIndex
from odoo.addons.plasticos_transaction.models import native_document_import

CUSTOMER, VENDOR, CARRIER = "1577", "2213", "1495"
partner_model = env["res.partner"]
customer = partner_model.create({"name": "Probe Customer 1577", "is_company": True, "customer_rank": 1})
vendor = partner_model.create({"name": "Probe Vendor 2213", "is_company": True, "supplier_rank": 1})
carrier = partner_model.create({"name": "Probe Carrier 1495", "is_company": True, "supplier_rank": 1})
partner_by_cp = {CUSTOMER: customer.id, VENDOR: vendor.id, CARRIER: carrier.id}

index = SourceIndex()
index.orders["6345"] = {
    "POID": "6345",
    "PONumber": "14263",
    "Source": "SO",
    "CpID": CUSTOMER,
    "PriceBasis": "FOB Supplier Dock",
    "PODate": "2022-02-18 00:00:00",
    "POReference": "",
}
index.orders["6344"] = {
    "POID": "6344",
    "PONumber": "7275",
    "Source": "PO",
    "CpID": VENDOR,
    "PriceBasis": "FOB Supplier Dock",
    "PODate": "2022-02-18 00:00:00",
    "POReference": "",
}
index.orders_by_source_number = {("SO", "14263"): ["6345"], ("PO", "7275"): ["6344"]}
index.order_lines["9227"] = {"PONumber": "14263"}
index.order_lines["9226"] = {"PONumber": "7275"}
detail = {
    "DetailID": "6702",
    "BuySellNo": "54839",
    "SPO_ID": "9227",
    "PPO_ID": "9226",
    "GradeID": "PP-REGRIND",
    "InvoiceDesc": "PP regrind",
    "SWeight": "19145",
    "SWeightUOM": "L",
    "SAmount": "9763.95",
    "SPrice": "",
    "PWeight": "19188",
    "PWeightUOM": "L",
    "PAmount": "8826.48",
    "PPrice": "",
}
index.lines["6702"] = detail
index.lines_by_buysell["54839"] = ["6702"]
index.buysells["54839"] = {
    "BuySellNo": "54839",
    "CustID": CUSTOMER,
    "VendorID": VENDOR,
    "OrderDt": "2022-02-18 00:00:00",
    "InvoiceDt": "2022-04-01 00:00:00",
    "status": "I",
    "PriceBasis": "FOB Supplier Dock",
    "ProblemNotes": "",
    "Notes": "",
    "BookingNo": "",
    "ReferrerNo1": None,
    "Commission1": None,
    "ReferrerNo2": None,
    "Commission2": None,
}
index.payables_by_buysell["54839"] = [
    {
        "PayableID": "591398",
        "BuySellNo": "54839",
        "ItemID": "",
        "CpID": VENDOR,
        "Amount": "8826.48",
        "InvoiceNo": "V-7275",
        "InvoiceDt": "2022-03-15 00:00:00",
        "APBatchNo": "107184",
        "GLAcct": "50100",
    }
]
index.payables_batches["107184"] = {
    "APBatchNo": "107184",
    "InvoiceNo": "V-7275",
    "InvoiceDt": "2022-03-15 00:00:00",
    "DueDate": "2022-03-20 00:00:00",
    "APTerms": "No Such Term",
}
index.ledger_by_buysell["54839"] = [
    {
        "LedgerID": "5462",
        "BuySellNo": "54839",
        "Source": "B",
        "Sale": "9763.95",
        "Cost": "8826.48",
        "AdjType": None,
        "AdjApproved": None,
        "AdjCpID": CUSTOMER,
        "AdjMemoNo": "",
        "AdjDocTitle": "",
        "TradeDt": "2022-05-12 00:00:00",
    }
]

report = ImportReport()
native_document_import.realize(
    env["plasticos.erp.import"], index, report, partner_by_cp, None, False, False
)


def marker(model, res_id):
    rows = env["ir.model.data"].search([("model", "=", model), ("res_id", "=", res_id)])
    return [f"{row.module}.{row.name}" for row in rows]


def line_flag(move):
    line = move.invoice_line_ids[:1]
    if not line:
        return {"lines": 0}
    field = line._fields.get("is_imported")
    owner = None
    if field is not None:
        data = env["ir.model.data"].search(
            [("model", "=", "ir.model.fields"), ("res_id", "=", env["ir.model.fields"]._get("account.move.line", "is_imported").id)],
            limit=1,
        )
        owner = f"{data.module}.{data.name}" if data else "no-xmlid"
    return {
        "lines": len(move.invoice_line_ids),
        "is_imported_defined": field is not None,
        "is_imported": bool(line.is_imported) if field is not None else None,
        "is_imported_xmlid": owner,
        "sale_line_ids": line.sale_line_ids.ids,
    }


def describe_move(move):
    return {
        "id": move.id,
        "move_type": move.move_type,
        "state": move.state,
        "name": move.name,
        "ref": move.ref or "",
        "invoice_origin": move.invoice_origin or "",
        "invoice_date": str(move.invoice_date or ""),
        "invoice_date_due": str(move.invoice_date_due or ""),
        "payment_term": move.invoice_payment_term_id.display_name or "",
        "xmlids": marker("account.move", move.id),
        "move_has_is_imported": "is_imported" in move._fields,
        "lines": line_flag(move),
    }


def by_xmlid(name):
    data = env["ir.model.data"].search(
        [("module", "=", "plasticos_transaction"), ("name", "=", name), ("model", "=", "account.move")],
        limit=1,
    )
    return env["account.move"].browse(data.res_id) if data else env["account.move"]


historical_invoice = by_xmlid("legacy_erp_outinv_54839")
historical_bill = by_xmlid("legacy_erp_ininv_591398")
sale_data = env["ir.model.data"].search(
    [("module", "=", "plasticos_transaction"), ("name", "=", "legacy_erp_so_14263"), ("model", "=", "sale.order")],
    limit=1,
)
sale = env["sale.order"].browse(sale_data.res_id) if sale_data else env["sale.order"]
operational = sale._create_invoices() if sale else env["account.move"]
manual = env["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": customer.id,
        "invoice_origin": sale.name if sale else "MANUAL",
        "invoice_date": "2026-10-24",
        "invoice_line_ids": [(0, 0, {"name": "Manual line", "quantity": 1, "price_unit": 10.0})],
    }
)
tx = env["plasticos.transaction"].search([("name", "=", "54839")], limit=1)
print(
    "PROVENANCE "
    + json.dumps(
        {
            "head": "cc3f8cbb90d7f57c58de75af9d893d8ac2ed4c79",
            "sale": {
                "name": sale.name,
                "origin": sale.origin or "",
                "state": sale.state,
                "xmlids": marker("sale.order", sale.id),
                "transaction_id": sale.transaction_id.id,
                "transaction_name": sale.transaction_id.name or "",
            },
            "transaction": {
                "name": tx.name or "",
                "state": tx.state or "",
                "customer_invoice_xmlids": marker("account.move", tx.customer_invoice_id.id) if tx.customer_invoice_id else [],
                "vendor_bill_xmlids": [marker("account.move", bill.id) for bill in tx.vendor_bill_ids],
            },
            "historical_invoice": describe_move(historical_invoice),
            "historical_bill": describe_move(historical_bill),
            "operational_from_sale": [describe_move(move) for move in operational],
            "manual_invoice": describe_move(manual),
        },
        default=str,
    )
)
env.cr.rollback()
