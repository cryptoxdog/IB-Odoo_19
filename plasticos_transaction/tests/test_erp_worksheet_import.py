"""ERP worksheet import against the real ORM.

These run under ``odoo --test-enable --test-tags /plasticos_transaction`` on a
database that carries the PlasticOS stack. The source rows are built in the
test from the shapes the SQL projections return; no source database is read.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from odoo import Command
from odoo.addons.plasticos_partner_import.erp import source_index as erp_source_index
from odoo.addons.plasticos_partner_import.erp import summary
from odoo.addons.plasticos_partner_import.erp.reader import PayloadKind, SourcePayload
from odoo.addons.plasticos_partner_import.erp.report import ImportReport
from odoo.addons.plasticos_partner_import.erp.source_index import SourceIndex
from odoo.tests import TransactionCase, tagged

from ..models import native_document_import

XMLID_MODULE = native_document_import.XMLID_MODULE
CUSTOMER = "1577"
VENDOR = "2213"
CARRIER = "1495"
OTHER_CUSTOMER = "1974"


def _order(poid, number, source, cp_id, po_date, basis="FOB Supplier Dock"):
    return {
        "POID": poid,
        "PONumber": number,
        "Source": source,
        "CpID": cp_id,
        "PriceBasis": basis,
        "PODate": po_date,
        "POReference": "",
    }


def _line(detail_id, number, spo, ppo, sweight, samount, pweight, pamount, grade="PP-REGRIND"):
    return {
        "DetailID": detail_id,
        "BuySellNo": number,
        "SPO_ID": spo,
        "PPO_ID": ppo,
        "GradeID": grade,
        "InvoiceDesc": "PP regrind",
        "SWeight": sweight,
        "SWeightUOM": "L",
        "SAmount": samount,
        "SPrice": "",
        "PWeight": pweight,
        "PWeightUOM": "L",
        "PAmount": pamount,
        "PPrice": "",
    }


def _buysell(number, order_dt, cust=CUSTOMER, vendor=VENDOR, status="I", **slots):
    row = {
        "BuySellNo": number,
        "CustID": cust,
        "VendorID": vendor,
        "OrderDt": order_dt,
        "InvoiceDt": order_dt,
        "status": status,
        "PriceBasis": "FOB Supplier Dock",
        "ProblemNotes": "",
        "Notes": "",
        "BookingNo": "",
        "ReferrerNo1": None,
        "Commission1": None,
        "ReferrerNo2": None,
        "Commission2": None,
    }
    row.update(slots)
    return row


def _payable(payable_id, number, cp_id, amount, gl, invoice_no="", batch="", item=""):
    return {
        "PayableID": payable_id,
        "BuySellNo": number,
        "ItemID": item,
        "CpID": cp_id,
        "Amount": amount,
        "InvoiceNo": invoice_no,
        "InvoiceDt": "2022-04-01 00:00:00",
        "APBatchNo": batch,
        "GLAcct": gl,
    }


def _ledger(ledger_id, number, source, adj_type, approved, sale="0", cost="0", cp_id=CUSTOMER, memo="", title=""):
    return {
        "LedgerID": ledger_id,
        "BuySellNo": number,
        "Source": source,
        "Sale": sale,
        "Cost": cost,
        "AdjType": adj_type,
        "AdjApproved": approved,
        "AdjCpID": cp_id,
        "AdjMemoNo": memo,
        "AdjDocTitle": title,
        "TradeDt": "2022-05-12 00:00:00",
    }


@tagged("post_install", "-at_install")
def _origin_key(origin):
    """Total order over Odoo Char values that may be False."""
    return (origin is not False, origin or "")


class TestErpWorksheetImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.importer = cls.env["plasticos.erp.import"]
        cls.Transaction = cls.env["plasticos.transaction"]
        cls.Move = cls.env["account.move"]
        cls.Data = cls.env["ir.model.data"]
        cls.income = cls.env.ref("plasticos_accounting.account_40050_sales_income")
        cls.material = cls.env.ref("plasticos_accounting.account_50100_material_cost")
        cls.freight = cls.env.ref("plasticos_accounting.account_50200_freight_cost")
        Partner = cls.env["res.partner"]
        cls.customer = Partner.create({"name": "ERP Customer 1577", "is_company": True, "customer_rank": 1})
        cls.vendor = Partner.create({"name": "ERP Vendor 2213", "is_company": True, "supplier_rank": 1})
        cls.carrier = Partner.create({"name": "ERP Carrier 1495", "is_company": True, "supplier_rank": 1})
        cls.other_customer = Partner.create({"name": "ERP Customer 1974", "is_company": True, "customer_rank": 1})
        cls.partner_by_cp = {
            CUSTOMER: cls.customer.id,
            VENDOR: cls.vendor.id,
            CARRIER: cls.carrier.id,
            OTHER_CUSTOMER: cls.other_customer.id,
        }
        # The importer matches a worksheet recipient to the single user carrying
        # that name; a second user with the same name would make the lookup
        # ambiguous, so the seeded representative is reused when present.
        cls.rep_tf = cls.env["res.users"].search([("name", "=", "Tiffany White")], limit=1) or cls.env[
            "res.users"
        ].create(
            {
                "name": "Tiffany White",
                "login": "erp_tf_test",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )

    # ── fixtures ────────────────────────────────────────────────────────────
    def _index(self):
        index = SourceIndex()
        index.orders_by_source_number = {}
        return index

    def _add_order(self, index, poid, number, source, cp_id, po_date="2022-02-18 00:00:00"):
        index.orders[poid] = _order(poid, number, source, cp_id, po_date)
        index.orders_by_source_number.setdefault((source, number), []).append(poid)

    def _add_line(self, index, line_key, order_number, detail):
        index.order_lines[line_key] = {"PONumber": order_number}
        index.lines[detail["DetailID"]] = detail
        index.lines_by_buysell.setdefault(detail["BuySellNo"], []).append(detail["DetailID"])

    def _worksheet_54839(self, index):
        """Worksheet 54839: SO 14263 / PO 7275, 19,145 lb sold for 9,763.95, 19,188 lb bought for 8,826.48."""
        self._add_order(index, "6345", "14263", "SO", CUSTOMER)
        self._add_order(index, "6344", "7275", "PO", VENDOR)
        index.order_lines["9227"] = {"PONumber": "14263"}
        index.order_lines["9226"] = {"PONumber": "7275"}
        detail = _line("6702", "54839", "9227", "9226", "19145", "9763.95", "19188", "8826.48")
        index.lines["6702"] = detail
        index.lines_by_buysell["54839"] = ["6702"]
        index.buysells["54839"] = _buysell(
            "54839", "2022-02-18 00:00:00", ReferrerNo2="TF", Commission2="55.457", InvoiceDt="2022-04-01 00:00:00"
        )
        index.payables_by_buysell["54839"] = [
            _payable("591398", "54839", VENDOR, "9366.52", "50100", "7275"),
            _payable("591476", "54839", VENDOR, "-9366.52", "50100", "U-7275"),
            _payable("594620", "54839", VENDOR, "8826.48", "50100", "7275-B"),
            _payable("600001", "54839", CARRIER, "625", "50200", "FRT-1"),
            _payable("600002", "54839", CARRIER, "-25", "50200", "FRT-1-CR"),
            _payable("600003", "54839", VENDOR, "100", "50300", "HANDLING"),
            _payable("600004", "54839", VENDOR, "5000", "50100", "PREPAY", batch="PP-1"),
            # A posted vendor invoice whose GL lookup is blank on the row and on its delivery item.
            _payable("600009", "54839", VENDOR, "40", "", "PALLETS-9"),
        ]
        index.prepay_batches.add("PP-1")
        index.ledger_by_buysell["54839"] = [
            _ledger("5462", "54839", "B", None, None, sale="9763.95", cost="8826.48"),
            _ledger("5694", "54839", "A", "S", "Y", sale="-382.90", memo="CM 54839", title="CREDIT MEMO"),
            _ledger("5695", "54839", "A", "P", "Y", cost="-9366.52", cp_id=VENDOR),
            _ledger("5696", "54839", "A", "S", "N", sale="-1"),
            _ledger("5697", "54839", "D", "S", "Y", sale="-45.11"),
            # An approved positive sale-side adjustment is a customer debit memo on the invoice.
            _ledger("5698", "54839", "A", "S", "Y", sale="150", memo="DM 54839", title="DEBIT MEMO"),
        ]
        index.deliveries_by_buysell["54839"] = [
            {"BuySellNo": "54839", "GLAcct": "50200", "Cost": "625", "VendorID": CARRIER, "TrailerNo": "TRL-1"}
        ]

    def _run(self, index, limit=None):
        report = ImportReport()
        native_document_import.realize(self.importer, index, report, dict(self.partner_by_cp), limit, False, False)
        return report

    def _marked(self, model_name, prefix):
        data = self.Data.search(
            [("module", "=", XMLID_MODULE), ("model", "=", model_name), ("name", "=like", f"{prefix}%")]
        )
        return self.env[model_name].browse(data.mapped("res_id")).exists()

    def _snapshot(self):
        rows = self.Data.search_read([("module", "=", XMLID_MODULE)], ["name", "model", "res_id"], order="name")
        moves = self._marked("account.move", "legacy_erp_")
        return {
            "markers": [(row["name"], row["model"], row["res_id"]) for row in rows],
            "transactions": sorted(
                (tx.name, tx.state, tx.sale_order_id.id, tuple(tx.purchase_order_ids.ids), tx.customer_invoice_id.id)
                for tx in self.Transaction.search([])
            ),
            "moves": sorted((move.id, move.move_type, move.state, round(move.amount_total, 2)) for move in moves),
            # S6: orders that already exist may have no origin (False). Sort False before text,
            # keeping every value, so the whole-database replay comparison stays exact.
            "sale_origins": sorted(self.env["sale.order"].search([]).mapped("origin"), key=_origin_key),
            "purchase_origins": sorted(self.env["purchase.order"].search([]).mapped("origin"), key=_origin_key),
        }

    # ── F1: tax configuration is never written ──────────────────────────────
    def test_import_leaves_tax_configuration_alone_and_imports_without_taxes(self):
        company = self.env.company
        tax = self.env["account.tax"].create(
            {"name": "ERP test tax", "amount": 7.0, "type_tax_use": "sale", "company_id": company.id}
        )
        company.write({"account_sale_tax_id": tax.id})
        self.income.write({"tax_ids": [Command.set([tax.id])]})
        template = self.env["product.template"].create(
            {"name": "Taxed catalogue item", "taxes_id": [Command.set([tax.id])]}
        )
        taxed_accounts_before = self.env["account.account"].search_count([("tax_ids", "!=", False)])

        index = self._index()
        self._worksheet_54839(index)
        self._run(index)

        self.assertEqual(company.account_sale_tax_id, tax)
        self.assertEqual(self.income.tax_ids, tax)
        self.assertEqual(template.taxes_id, tax)
        self.assertEqual(self.env["account.account"].search_count([("tax_ids", "!=", False)]), taxed_accounts_before)
        moves = self._marked("account.move", "legacy_erp_")
        self.assertTrue(moves)
        self.assertFalse(moves.invoice_line_ids.tax_ids, "imported document lines carry no tax")
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_").order_line.tax_ids)
        self.assertFalse(self._marked("purchase.order", "legacy_erp_po_").order_line.tax_ids)

    # ── F2: no fabricated settlement ────────────────────────────────────────
    def test_historical_documents_stay_draft_with_no_settlement_entries(self):
        payments_before = self.env["account.payment"].search_count([])
        entries_before = self.Move.search_count([("move_type", "=", "entry")])
        index = self._index()
        self._worksheet_54839(index)
        self._run(index)

        moves = self._marked("account.move", "legacy_erp_")
        self.assertTrue(moves)
        self.assertEqual(set(moves.mapped("state")), {"draft"})
        self.assertEqual(self.env["account.payment"].search_count([]), payments_before)
        self.assertEqual(self.Move.search_count([("move_type", "=", "entry")]), entries_before)
        self.assertFalse(self.env["account.move.line"].search([("name", "=", "Historical settlement")]))
        self.assertFalse(moves.line_ids.filtered(lambda line: line.account_id.account_type == "equity_unaffected"))
        self.assertFalse(moves.line_ids.filtered("reconciled"))

    # ── PR 3a: source header facts, PO approval date, no stock event ───────
    def test_bills_take_header_facts_and_orders_keep_draft_with_no_stock_event(self):
        """Header date, vendor invoice number, terms or due date; PO approved at TradeDt; nothing ships."""
        thirty = self.env.ref("account.account_payment_term_30days")
        pickings_before = self.env["stock.picking"].search_count([])
        stock_moves_before = self.env["stock.move"].search_count([])
        index = self._index()
        self._worksheet_54839(index)
        rows = {row["PayableID"]: row for row in index.payables_by_buysell["54839"]}
        rows["591398"]["APBatchNo"] = "107184"
        rows["594620"]["APBatchNo"] = "107367"
        index.payables_batches["107184"] = {
            "APBatchNo": "107184",
            "InvoiceNo": "V-7275",
            "InvoiceDt": "2022-03-15 00:00:00",
            "DueDate": "2022-03-20 00:00:00",
            "APTerms": "No Such Term",
        }
        index.payables_batches["107367"] = {
            "APBatchNo": "107367",
            "InvoiceNo": "V-7275-B",
            "InvoiceDt": "2022-04-14 00:00:00",
            "DueDate": "2022-04-14 00:00:00",
            "APTerms": thirty.name,
        }
        report = self._run(index)

        unmatched = self._marked("account.move", "legacy_erp_ininv_591398")
        self.assertEqual(unmatched.ref, "V-7275")
        self.assertEqual(unmatched.invoice_date, date(2022, 3, 15))
        self.assertFalse(unmatched.invoice_payment_term_id, "the partner's default term must not replace DueDate")
        self.assertEqual(unmatched.invoice_date_due, date(2022, 3, 20))
        termed = self._marked("account.move", "legacy_erp_ininv_594620")
        self.assertEqual(termed.ref, "V-7275-B")
        self.assertEqual(termed.invoice_payment_term_id, thirty)
        self.assertEqual(termed.invoice_date_due, date(2022, 5, 14), "the named term computes the due date")
        headerless = self._marked("account.move", "legacy_erp_ininv_600001")
        self.assertEqual(headerless.ref, "FRT-1", "a row without a batch header keeps its own invoice number")
        self.assertEqual(headerless.invoice_date, date(2022, 4, 1))
        term_anomalies = [a for a in report.anomalies if "no account.payment.term named 'No Such Term'" in a["detail"]]
        self.assertEqual(len(term_anomalies), 1, "an unmatched term name is reported once")

        purchase = self._marked("purchase.order", "legacy_erp_po_7275")
        self.assertEqual(purchase.state, "draft")
        self.assertEqual(purchase.date_approve, datetime(2022, 5, 12), "earliest GPLedger.TradeDt")
        self.assertFalse(purchase.picking_ids)
        sale = self._marked("sale.order", "legacy_erp_so_14263")
        self.assertEqual(sale.state, "sale")
        if "picking_ids" in sale._fields:
            self.assertFalse(sale.picking_ids, "a historical sale is not shipped again")
        self.assertEqual(self.env["stock.picking"].search_count([]), pickings_before)
        self.assertEqual(self.env["stock.move"].search_count([]), stock_moves_before)
        moves = self._marked("account.move", "legacy_erp_")
        self.assertEqual(set(moves.mapped("state")), {"draft"})

    def test_delivered_basis_sets_no_incoterm_and_undated_invoice_stays_undated(self):
        index = self._index()
        self._worksheet_54839(index)
        index.orders["6345"]["PriceBasis"] = "Delivered"
        index.buysells["54839"]["InvoiceDt"] = None
        for row in index.ledger_by_buysell["54839"]:
            row["TradeDt"] = None
        report = self._run(index)

        purchase = self._marked("purchase.order", "legacy_erp_po_7275")
        self.assertFalse(purchase.date_approve, "no trade date is never replaced by another date")
        self.assertIn(
            "purchase.order 7275: date_approve not set (no GPLedger trade date)",
            [anomaly["detail"] for anomaly in report.anomalies],
        )

        sale = self._marked("sale.order", "legacy_erp_so_14263")
        if "incoterm" in sale._fields:
            self.assertFalse(sale.incoterm, "Delivered is not FAS")
        details = [anomaly["detail"] for anomaly in report.anomalies]
        self.assertIn("sale.order 14263: price basis 'Delivered' has no supported Incoterm; none set", details)
        invoice = self._marked("account.move", "legacy_erp_outinv_54839")
        self.assertFalse(invoice.invoice_date, "never the worksheet order date")
        self.assertIn("no source invoice date; customer invoice left undated", details)

    # ── F5: credits, freight, costs, prepay exclusion ──────────────────────
    def test_worksheet_54839_keeps_credit_freight_costs_and_excludes_prepay(self):
        index = self._index()
        self._worksheet_54839(index)
        report = self._run(index)

        tx = self.Transaction.search([("name", "=", "54839")])
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx.state, "closed")
        self.assertEqual(tx.buyer_id, self.customer)
        self.assertEqual(tx.supplier_id, self.vendor)
        self.assertEqual(tx.carrier_id, self.carrier)
        self.assertEqual(tx.sale_order_id.name, "14263")
        self.assertEqual(tx.purchase_order_ids.mapped("name"), ["7275"])
        self.assertAlmostEqual(tx.sale_order_id.order_line.product_uom_qty, 19145.0)
        self.assertAlmostEqual(tx.purchase_order_ids.order_line.product_qty, 19188.0)

        invoice = tx.customer_invoice_id
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertAlmostEqual(invoice.amount_total, 9763.95, places=2)
        credit = self._marked("account.move", "legacy_erp_ledger_5694")
        self.assertEqual(credit.move_type, "out_refund")
        self.assertAlmostEqual(credit.amount_total, 382.90, places=2)
        self.assertEqual(credit.reversed_entry_id, invoice)
        self.assertEqual(credit.partner_id, self.customer)
        self.assertEqual(credit.invoice_line_ids.account_id, self.income)
        debit = self._marked("account.move", "legacy_erp_ledger_5698")
        self.assertEqual(debit.move_type, "out_invoice")
        self.assertAlmostEqual(debit.amount_total, 150.0, places=2)
        self.assertEqual(debit.debit_origin_id, invoice)
        self.assertEqual(invoice.debit_note_ids, debit)
        self.assertEqual(invoice.reversal_move_ids, credit)
        # Revenue is the customer document set, each document once: the invoice,
        # plus its debit memo, minus its credit note.
        self.assertAlmostEqual(tx.revenue_total, 9763.95 + 150.0 - 382.90, places=2)
        self.assertAlmostEqual(
            tx.revenue_total, invoice.amount_total + debit.amount_total - credit.amount_total, places=2
        )

        bills = tx.vendor_bill_ids
        self.assertEqual(len(bills), 3)
        self.assertEqual(sorted(bills.mapped("move_type")), ["in_invoice", "in_invoice", "in_refund"])
        self.assertEqual(set(bills.invoice_line_ids.mapped("account_id").ids), {self.material.id})
        self.assertAlmostEqual(tx.purchase_cost_total, 8826.48, places=2)

        freight_bills = tx.freight_bill_ids
        self.assertEqual(len(freight_bills), 2)
        self.assertEqual(set(freight_bills.mapped("partner_id").ids), {self.carrier.id})
        self.assertEqual(set(freight_bills.invoice_line_ids.mapped("account_id").ids), {self.freight.id})
        self.assertFalse(self.material in freight_bills.invoice_line_ids.mapped("account_id"))
        self.assertAlmostEqual(tx.freight_cost_total, 600.0, places=2)
        self.assertAlmostEqual(tx.other_expenses, 100.0, places=2)
        self.assertAlmostEqual(tx.gross_margin, (9763.95 + 150.0 - 382.90) - 8826.48 - 600.0 - 100.0, places=2)

        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_600004"), "prepay batch row is not a bill")
        self.assertFalse(
            self._marked("account.move", "legacy_erp_ledger_5695"), "vendor adjustment is carried by Payables"
        )
        self.assertFalse(
            self._marked("account.move", "legacy_erp_ledger_5696"), "unapproved adjustment is not a document"
        )
        self.assertFalse(self._marked("account.move", "legacy_erp_ledger_5697"), "discount row is settlement evidence")
        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_600009"), "blank-GL row is not a bill")
        details = {(item["table"], item["key"], item["detail"]) for item in report.anomalies}
        self.assertIn(("GPLedger", "5696", "unapproved adjustment omitted"), details)
        self.assertIn(("GPLedger", "5697", "Source D row is settlement evidence"), details)
        self.assertIn(
            (
                "Payables",
                "600003",
                "transaction_only_cost: GL 50300 has no native account in the crosswalk; amount carried once as"
                " other expenses; vendor 2213 invoice HANDLING dated 2022-04-01 amount 100.00 worksheet 54839",
            ),
            details,
        )
        self.assertIn(
            (
                "Payables",
                "600009",
                "not_realized: GL lookup blank resolves no native account; not realized, not counted;"
                " vendor 2213 invoice PALLETS-9 dated 2022-04-01 amount 40.00 worksheet 54839",
            ),
            details,
        )
        self.assertIn(
            (
                "Payables",
                "600004",
                "prepay_omitted: APBatchNo PP-1 is a PrePay=1 batch; vendor 2213 invoice PREPAY dated 2022-04-01"
                " amount 5000.00 worksheet 54839",
            ),
            details,
        )
        payables = report.census["payables"]
        self.assertEqual(payables["gl_50100_billed"], {"rows": 3, "worksheets": 1, "amount": 8826.48})
        self.assertEqual(payables["gl_50200_billed"], {"rows": 2, "worksheets": 1, "amount": 600.0})
        self.assertEqual(payables["gl_50300_as_other_expenses"], {"rows": 1, "worksheets": 1, "amount": 100.0})
        self.assertEqual(payables["gl_blank_not_realized"], {"rows": 1, "worksheets": 1, "amount": 40.0})
        self.assertEqual(payables["prepay_batch_omitted"], {"rows": 1, "worksheets": 1, "amount": 5000.0})
        # Every row the import did not write is quarantined with its full source identity.
        quarantine = {entry["payable_id"]: entry for entry in report.census["unresolved_bills"]}
        self.assertEqual(sorted(quarantine), ["600003", "600004", "600009"])
        self.assertEqual(
            quarantine["600009"],
            {
                "payable_id": "600009",
                "worksheet": "54839",
                "vendor": VENDOR,
                "invoice_no": "PALLETS-9",
                "invoice_date": "2022-04-01",
                "amount": 40.0,
                "gl": "",
                "batch": "",
                "reason": "GL lookup blank resolves no native account; not realized, not counted",
                "disposition": "not_realized",
            },
        )
        self.assertEqual(quarantine["600003"]["disposition"], "transaction_only_cost")
        self.assertEqual(quarantine["600003"]["gl"], "50300")
        self.assertEqual(quarantine["600004"]["disposition"], "prepay_omitted")
        self.assertEqual(quarantine["600004"]["batch"], "PP-1")
        # Billed rows plus quarantined rows account for every payable row of the worksheet.
        reconciliation = report.census["payables_reconciliation"]
        self.assertEqual(reconciliation["rows_seen"], 8)
        self.assertEqual(reconciliation["billed_rows"], 5)
        self.assertAlmostEqual(reconciliation["billed_amount"], 8826.48 + 600.0, places=2)
        self.assertEqual(reconciliation["quarantined_rows"], 3)
        self.assertAlmostEqual(reconciliation["quarantined_amount"], 5140.0, places=2)
        self.assertEqual(
            reconciliation["by_disposition"],
            {
                "not_realized": {"rows": 1, "amount": 40.0},
                "prepay_omitted": {"rows": 1, "amount": 5000.0},
                "transaction_only_cost": {"rows": 1, "amount": 100.0},
            },
        )
        self.assertTrue(reconciliation["closes"])
        self.assertNotIn("reconciliation", {item["key"] for item in report.anomalies})
        # The blank-GL amount is in no economic total: not a bill, not other expenses.
        self.assertAlmostEqual(tx.cost_total, 8826.48 + 600.0 + 100.0, places=2)
        self.assertEqual(report.census["price_precision"]["lines"], 0, "0.51/lb and 0.46/lb store exactly")
        self.assertEqual(report.census["worksheets"]["without_sale_link"]["worksheets"], 0)

    def test_unbilled_freight_row_is_not_folded_beside_freight_bills(self):
        """Freight is counted once: a freight row with no vendor is an exception, not a second cost."""
        index = self._index()
        self._worksheet_54839(index)
        index.payables_by_buysell["54839"].append(_payable("600005", "54839", "9999", "-75", "50200", "FRT-X"))
        report = self._run(index)

        tx = self.Transaction.search([("name", "=", "54839")])
        self.assertEqual(len(tx.freight_bill_ids), 2)
        self.assertAlmostEqual(tx.freight_cost_total, 600.0, places=2)
        self.assertAlmostEqual(tx.freight_actual, 0.0, places=2)
        details = {(item["table"], item["key"], item["detail"]) for item in report.anomalies}
        self.assertIn(("BuySell", "54839", "unbilled freight -75.00 not counted: worksheet has freight bills"), details)
        self.assertEqual(report.census["payables"]["gl_50200_unbilled"], {"rows": 1, "worksheets": 1, "amount": -75.0})
        entry = {e["payable_id"]: e for e in report.census["unresolved_bills"]}["600005"]
        self.assertEqual(entry["disposition"], "unbillable")
        self.assertEqual(
            entry["reason"], "vendor 9999 is not an imported counterparty; not counted: worksheet has freight bills"
        )
        self.assertTrue(report.census["payables_reconciliation"]["closes"])

    # ── GMP-002: payable coverage and economic dispositions ────────────────
    def _payable_set(self, number, vendor=VENDOR):
        """One material bill, one handling row, one blank-GL row, one unbillable freight credit."""
        return [
            _payable(f"8{number}1", number, vendor, "1000", "50100", f"INV-{number}"),
            _payable(f"8{number}2", number, vendor, "80", "50300", f"HND-{number}"),
            _payable(f"8{number}3", number, vendor, "40", "", f"PLT-{number}"),
            _payable(f"8{number}4", number, "9999", "-30", "50200", f"FRT-{number}"),
        ]

    def _quarantine_by_id(self, report):
        return {entry["payable_id"]: entry for entry in report.census["unresolved_bills"]}

    def test_no_link_worksheet_quarantines_every_source_payable(self):
        """A worksheet with no valid order link realizes nothing; each of its bills is reported, none counted."""
        index = self._index()
        # The commercial graph is present (an unrelated order), so realization runs; the worksheet's
        # own line names no order on either side.
        self._add_order(index, "9000", "16000", "SO", CUSTOMER, "2021-06-01 00:00:00")
        self._add_line(index, "9900", "x", _line("14000", "60800", "", "", "1000", "500", "1000", "400"))
        index.order_lines.pop("9900", None)
        index.buysells["60800"] = _buysell("60800", "2021-06-01 00:00:00")
        index.payables_by_buysell["60800"] = self._payable_set("60800")
        report = self._run(index)

        self.assertEqual(report.counts["transactions"]["rejected"], 1)
        self.assertEqual(report.counts["transactions"]["created"], 0)
        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_"))
        self.assertFalse(self._marked("purchase.order", "legacy_erp_po_"))
        quarantine = self._quarantine_by_id(report)
        self.assertEqual(sorted(quarantine), ["8608001", "8608002", "8608003", "8608004"])
        for entry in quarantine.values():
            self.assertEqual(entry["disposition"], "not_realized")
            self.assertEqual(entry["worksheet"], "60800")
            self.assertEqual(
                entry["reason"],
                "worksheet has no valid sale or purchase order link; no document to attach the bill to",
            )
        self.assertEqual(quarantine["8608001"]["invoice_no"], "INV-60800")
        self.assertEqual(quarantine["8608001"]["amount"], 1000.0)
        reconciliation = report.census["payables_reconciliation"]
        self.assertEqual(reconciliation["rows_seen"], 4)
        self.assertEqual(reconciliation["billed_rows"], 0)
        self.assertEqual(reconciliation["quarantined_rows"], 4)
        self.assertAlmostEqual(reconciliation["quarantined_amount"], 1090.0, places=2)
        self.assertTrue(reconciliation["closes"])
        self.assertEqual(
            report.census["payables"]["no_order_link_not_realized"], {"rows": 4, "worksheets": 1, "amount": 1090.0}
        )
        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(replay.counts["transactions"]["rejected"], 1)
        self.assertEqual(replay.census["payables_reconciliation"], reconciliation)

    def test_purchase_only_worksheet_carries_no_handling_or_equipment_cost(self):
        """Without a transaction there is nothing to carry a transaction-only cost; the bill is not realized."""
        index = self._index()
        self._add_order(index, "9650", "8051", "PO", VENDOR, "2021-07-01 00:00:00")
        self._add_line(index, "9850", "8051", _line("14010", "60810", "", "9850", "0", "0", "2000", "1000"))
        index.buysells["60810"] = _buysell("60810", "2021-07-01 00:00:00")
        index.payables_by_buysell["60810"] = [
            _payable("8608101", "60810", VENDOR, "1000", "50100", "INV-60810"),
            _payable("8608102", "60810", VENDOR, "80", "50300", "HND-60810"),
            _payable("8608105", "60810", VENDOR, "120", "50600", "EQP-60810"),
        ]
        report = self._run(index)

        self.assertFalse(self.Transaction.search([("name", "=", "60810")]))
        self.assertEqual(report.counts["transactions"]["rejected"], 1)
        bill = self._marked("account.move", "legacy_erp_ininv_8608101")
        self.assertAlmostEqual(bill.amount_total, 1000.0, places=2)
        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_8608102"))
        quarantine = self._quarantine_by_id(report)
        self.assertEqual(sorted(quarantine), ["8608102", "8608105"])
        for payable_id, gl in (("8608102", "50300"), ("8608105", "50600")):
            self.assertEqual(quarantine[payable_id]["disposition"], "not_realized")
            self.assertEqual(
                quarantine[payable_id]["reason"],
                f"GL {gl} has no native account in the crosswalk and no transaction exists to carry it",
            )
        payables = report.census["payables"]
        self.assertEqual(payables["gl_50300_not_realized"], {"rows": 1, "worksheets": 1, "amount": 80.0})
        self.assertEqual(payables["gl_50600_not_realized"], {"rows": 1, "worksheets": 1, "amount": 120.0})
        self.assertNotIn("gl_50300_as_other_expenses", payables)
        self.assertEqual(
            report.census["payables_reconciliation"]["by_disposition"], {"not_realized": {"rows": 2, "amount": 200.0}}
        )
        self.assertTrue(report.census["payables_reconciliation"]["closes"])
        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(replay.census["payables_reconciliation"], report.census["payables_reconciliation"])

    def test_unbillable_only_freight_is_carried_as_actual_freight_cost_when_a_transaction_exists(self):
        """No freight bill exists: the transaction's actual freight cost carries the amount once, and says so."""
        index = self._index()
        self._add_order(index, "9661", "16061", "SO", CUSTOMER, "2021-08-01 00:00:00")
        self._add_order(index, "9660", "8061", "PO", VENDOR, "2021-08-01 00:00:00")
        self._add_line(index, "9861", "16061", _line("14020", "60820", "9861", "9860", "1000", "500", "1000", "400"))
        index.order_lines["9860"] = {"PONumber": "8061"}
        index.buysells["60820"] = _buysell("60820", "2021-08-01 00:00:00")
        index.payables_by_buysell["60820"] = [
            _payable("8608201", "60820", VENDOR, "400", "50100", "INV-60820"),
            _payable("8608204", "60820", "9999", "55", "50200", "FRT-60820"),
        ]
        report = self._run(index)

        tx = self.Transaction.search([("name", "=", "60820")])
        self.assertEqual(len(tx), 1)
        self.assertFalse(tx.freight_bill_ids)
        self.assertAlmostEqual(tx.freight_actual, 55.0, places=2)
        self.assertAlmostEqual(tx.freight_cost_total, 55.0, places=2)
        self.assertAlmostEqual(tx.cost_total, 455.0, places=2)
        entry = self._quarantine_by_id(report)["8608204"]
        self.assertEqual(entry["disposition"], "transaction_only_cost")
        self.assertEqual(
            entry["reason"],
            "vendor 9999 is not an imported counterparty; amount carried once as the transaction's actual freight cost",
        )
        self.assertEqual(report.census["payables"]["gl_50200_unbilled"], {"rows": 1, "worksheets": 1, "amount": 55.0})
        self.assertTrue(report.census["payables_reconciliation"]["closes"])
        # Without a transaction the same row has nowhere to go and says so.
        self._add_order(index, "9670", "8071", "PO", VENDOR, "2021-08-02 00:00:00")
        self._add_line(index, "9870", "8071", _line("14021", "60821", "", "9870", "0", "0", "1000", "400"))
        index.buysells["60821"] = _buysell("60821", "2021-08-02 00:00:00")
        index.payables_by_buysell["60821"] = [_payable("8608214", "60821", "9999", "20", "50200", "FRT-60821")]
        second = self._run(index)
        self.assertFalse(self.Transaction.search([("name", "=", "60821")]))
        entry = self._quarantine_by_id(second)["8608214"]
        self.assertEqual(entry["disposition"], "not_realized")
        self.assertEqual(
            entry["reason"], "vendor 9999 is not an imported counterparty; no transaction exists to carry it"
        )
        self.assertTrue(second.census["payables_reconciliation"]["closes"])

    def test_payables_outside_the_worksheet_universe_and_rolled_back_worksheets_are_quarantined(self):
        """Exception totals cover rows the importer never visits and rows it rolled back; replay is stable."""
        index = self._index()
        self._worksheet_54839(index)
        # Rolled back: vendor 9999 is not an imported counterparty, so the PO cannot be written.
        self._add_order(index, "8101", "15101", "SO", CUSTOMER)
        self._add_order(index, "8100", "7400", "PO", "9999")
        self._add_line(index, "9500", "15101", _line("7101", "58001", "9500", "9501", "1000", "500", "1000", "400"))
        index.order_lines["9501"] = {"PONumber": "7400"}
        index.buysells["58001"] = _buysell("58001", "2024-03-01 00:00:00", vendor="9999")
        index.payables_by_buysell["58001"] = [_payable("8580011", "58001", VENDOR, "400", "50100", "INV-58001")]
        # Outside the universe: a free-text reference and a blank one.
        index.payables_by_buysell["51694 / 4714"] = [_payable("500868", "51694 / 4714", VENDOR, "168.72", "", "4714")]
        index.payables_by_buysell["52948INV"] = [_payable("500869", "52948INV", VENDOR, "-40", "", "AP-OFFSET")]
        index.payables_by_buysell[""] = [_payable("999001", "", VENDOR, "12.5", "50100", "NOREF")]
        report = self._run(index)

        self.assertEqual(report.counts["transactions"]["rejected"], 1)
        self.assertEqual(report.census["worksheets_rejected"], ["58001"])
        quarantine = self._quarantine_by_id(report)
        rolled = quarantine["8580011"]
        self.assertEqual(rolled["disposition"], "not_realized")
        self.assertEqual(rolled["reason"], "worksheet rolled back (ValueError); no document of it exists")
        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_8580011"))
        self.assertNotIn("500868", quarantine)
        self.assertNotIn("500869", quarantine)
        blank_bill = self._marked("account.move", "legacy_erp_ininv_500868")
        credit = self._marked("account.move", "legacy_erp_ininv_500869")
        self.assertEqual(blank_bill.move_type, "in_invoice")
        self.assertEqual(credit.move_type, "in_refund")
        self.assertEqual(blank_bill.state, "draft")
        self.assertEqual(blank_bill.invoice_origin, "51694 / 4714")
        self.assertEqual(credit.invoice_origin, "52948INV")
        self.assertEqual(blank_bill.partner_id, self.vendor)
        self.assertEqual(set(blank_bill.invoice_line_ids.account_id.ids), {self.material.id})
        self.assertEqual(set(credit.invoice_line_ids.account_id.ids), {self.material.id})
        self.assertAlmostEqual(blank_bill.amount_total, 168.72, places=2)
        self.assertAlmostEqual(credit.amount_total, 40.0, places=2)
        blank = quarantine["999001"]
        self.assertEqual(blank["worksheet"], "")
        self.assertEqual(
            blank["reason"],
            "blank BuySellNo; the bill names no worksheet"
            " (GL 50100 has a native account; realizing it standalone is an operator decision)",
        )
        payables = report.census["payables"]
        self.assertEqual(payables["worksheet_rolled_back_not_realized"], {"rows": 1, "worksheets": 1, "amount": 400.0})
        self.assertEqual(
            payables["outside_worksheet_universe_not_realized"], {"rows": 1, "worksheets": 1, "amount": 12.5}
        )
        reconciliation = report.census["payables_reconciliation"]
        self.assertEqual(reconciliation["rows_seen"], 8 + 1 + 3)
        self.assertEqual(reconciliation["billed_rows"], 7)
        self.assertEqual(reconciliation["quarantined_rows"], 5)
        self.assertTrue(reconciliation["closes"])
        self.assertEqual(report.census["payables_unselected"], {"rows": 0, "amount": 0.0})
        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(replay.census["payables_reconciliation"], reconciliation)
        self.assertEqual(replay.census["unresolved_bills"], report.census["unresolved_bills"])

    def test_diagnostic_limit_counts_the_payables_it_leaves_out(self):
        index = self._index()
        self._worksheet_54839(index)
        self._add_order(index, "9681", "16081", "SO", CUSTOMER, "2026-07-05 00:00:00")
        self._add_order(index, "9680", "8081", "PO", VENDOR, "2026-07-05 00:00:00")
        self._add_line(index, "9881", "16081", _line("14030", "60830", "9881", "9880", "1000", "500", "1000", "400"))
        index.order_lines["9880"] = {"PONumber": "8081"}
        index.buysells["60830"] = _buysell("60830", "2026-07-05 00:00:00")
        index.payables_by_buysell["60830"] = [_payable("8608301", "60830", VENDOR, "400", "50100", "INV-60830")]
        report = self._run(index, limit=1)

        self.assertEqual(report.counts["transactions"]["skipped"], 1, "54839 left out by the limit")
        # 9 366.52 − 9 366.52 + 8 826.48 + 625 − 25 + 100 + 5 000 + 40
        self.assertEqual(report.census["payables_unselected"], {"rows": 8, "amount": 14566.48})
        self.assertEqual(
            report.census["payables_excluded"],
            {"rows": 8, "amount": 14566.48, "by_reason": {"diagnostic_limit": {"rows": 8, "amount": 14566.48}}},
        )
        reconciliation = report.census["payables_reconciliation"]
        self.assertEqual(reconciliation["rows_seen"], 1)
        # The eight excluded rows are named by identity, so the source still reconciles: 9 = 1 + 0 + 8.
        self.assertEqual(reconciliation["source_rows"], 9)
        self.assertEqual(reconciliation["excluded_rows"], 8)
        self.assertEqual(reconciliation["missing_rows"], [])
        self.assertTrue(reconciliation["closes"])

    # ── GMP-003: payable coverage by identity, transaction verdict after confirm ──
    def _worksheet_with_sale_and_costs(self, index, number, so_poid, so_number, po_poid, po_number, day):
        """SO + PO linked worksheet with a material bill, a handling row (50300) and an unbillable freight row."""
        self._add_order(index, so_poid, so_number, "SO", CUSTOMER, day)
        self._add_order(index, po_poid, po_number, "PO", VENDOR, day)
        sale_key, purchase_key = f"9{so_poid}", f"9{po_poid}"
        self._add_line(
            index,
            sale_key,
            so_number,
            _line(f"14{number}", number, sale_key, purchase_key, "1000", "500", "1000", "400"),
        )
        index.order_lines[purchase_key] = {"PONumber": po_number}
        index.buysells[number] = _buysell(number, day)
        index.payables_by_buysell[number] = [
            _payable(f"8{number}1", number, VENDOR, "400", "50100", f"INV-{number}"),
            _payable(f"8{number}2", number, VENDOR, "80", "50300", f"HND-{number}"),
            _payable(f"8{number}4", number, "9999", "55", "50200", f"FRT-{number}"),
        ]

    def _anomaly_details(self, report):
        return {(item["table"], item["key"], item["detail"]) for item in report.anomalies}

    def test_empty_order_graph_quarantines_every_payable_and_still_reconciles(self):
        """No order header writes no worksheet. A blank-account bill with a vendor is still a bill."""
        index = self._index()
        self._add_line(index, "9900", "x", _line("14000", "60900", "9900", "9901", "1000", "500", "1000", "400"))
        index.order_lines.clear()
        index.buysells["60900"] = _buysell("60900", "2021-06-01 00:00:00")
        index.payables_by_buysell["60900"] = self._payable_set("60900")
        index.payables_by_buysell["51694 / 4714"] = [_payable("500868", "51694 / 4714", VENDOR, "168.72", "", "4714")]
        self.assertFalse(index.orders)
        report = self._run(index)

        self.assertEqual(report.counts["transactions"], {"created": 0, "updated": 0, "skipped": 1, "rejected": 0})
        blank_bill = self._marked("account.move", "legacy_erp_ininv_500868")
        self.assertEqual(blank_bill.move_type, "in_invoice")
        self.assertEqual(set(blank_bill.invoice_line_ids.account_id.ids), {self.material.id})
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_"))
        quarantine = self._quarantine_by_id(report)
        self.assertEqual(sorted(quarantine), ["8609001", "8609002", "8609003", "8609004"])
        for payable_id in ("8609001", "8609002", "8609003", "8609004"):
            self.assertEqual(quarantine[payable_id]["disposition"], "not_realized")
            self.assertEqual(
                quarantine[payable_id]["reason"], "source carries no order headers; no document to attach the bill to"
            )
        self.assertEqual(
            report.census["payables"]["no_order_link_not_realized"], {"rows": 4, "worksheets": 1, "amount": 1090.0}
        )
        reconciliation = report.census["payables_reconciliation"]
        self.assertEqual(reconciliation["source_rows"], 5)
        self.assertEqual(reconciliation["quarantined_rows"], 4)
        self.assertEqual((reconciliation["billed_rows"], reconciliation["excluded_rows"]), (1, 0))
        self.assertEqual(reconciliation["missing_rows"], [])
        self.assertTrue(reconciliation["closes"])
        self.assertNotIn("reconciliation", {item["key"] for item in report.anomalies})
        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(replay.census["payables_reconciliation"], reconciliation)

    def test_reconciliation_does_not_close_when_a_source_payable_is_on_neither_side(self):
        """Identity coverage catches what the routed count cannot: a row omitted from both tallies."""
        index = self._index()
        self._worksheet_54839(index)
        report = self._run(index)
        self.assertTrue(report.census["payables_reconciliation"]["closes"])
        # Rebuild the census from a context that lost one billed identity and never routed one row.
        context = native_document_import._load_context(self.importer)
        context["expense_rows"] = [("54839", "gl_50100_billed", 9366.52), ("54839", "gl_50100_billed", -9366.52)]
        context["billed_payables"] = [("54839", "591398"), ("54839", "591476")]
        census = native_document_import._census(index, context)
        reconciliation = census["payables_reconciliation"]
        self.assertEqual(
            reconciliation["rows_seen"], reconciliation["billed_rows"] + reconciliation["quarantined_rows"]
        )
        self.assertEqual(reconciliation["source_rows"], 8)
        self.assertEqual(reconciliation["unaccounted_rows"], 6)
        self.assertEqual(reconciliation["missing_rows"], ["594620", "600001", "600002", "600003", "600004", "600009"])
        self.assertFalse(reconciliation["closes"])
        # The same identity on both sides is a duplicate, not coverage.
        context["quarantine"] = [
            {"worksheet": "54839", "payable_id": "591398", "amount": 1.0, "disposition": "unbillable"}
        ]
        context["expense_rows"].append(("54839", "gl_50100_unbilled", 1.0))
        duplicated = native_document_import._census(index, context)["payables_reconciliation"]
        self.assertEqual(duplicated["duplicated_rows"], ["591398"])
        self.assertFalse(duplicated["closes"])
        # End to end: a source row with no PayableID cannot be proven covered, and the run says so.
        index.payables_by_buysell["54839"].append(_payable("", "54839", VENDOR, "7", "", "NO-ID"))
        unproven = self._run(index)
        self.assertEqual(unproven.census["payables_reconciliation"]["blank_identity_rows"], 1)
        self.assertFalse(unproven.census["payables_reconciliation"]["closes"])
        self.assertIn(
            ("Payables", "reconciliation", "1 source rows without a PayableID"), self._anomaly_details(unproven)
        )
        # GMP-004: the gap is a failure of the run, not a diagnostic. It reaches the machine-readable
        # summary and the exit status without relabelling a single row.
        self.assertEqual(
            unproven.failures,
            [
                {
                    "check": "payables_reconciliation",
                    "detail": "payables identity reconciliation does not close: 1 source rows without a PayableID",
                }
            ],
        )
        self.assertEqual(report.failures, [], "the closing run carries no failure")
        for outcome in (report, unproven):
            outcome.source_counts = index.counts()
        closing = summary.import_run_summary(report.as_dict())
        failing = summary.import_run_summary(unproven.as_dict())
        self.assertEqual(closing["final_status"], "success")
        self.assertEqual(failing["final_status"], "failed")
        # Same counters either way: the replay's rows are all unchanged, nothing is rejected to balance it.
        self.assertEqual(failing["records_rejected"], 0)
        self.assertEqual(failing["records_seen"], failing["records_unchanged"])
        self.assertEqual(
            [row["record_ref"] for row in failing["errors"]], ["payables_reconciliation"], "no counter gap, one failure"
        )
        self.assertEqual(len(unproven.census["unresolved_bills"]), len(report.census["unresolved_bills"]) + 1)
        self.assertEqual(summary.run_exit_status({**report.as_dict(), "summary": closing}), 0)
        self.assertEqual(summary.run_exit_status({**unproven.as_dict(), "summary": failing}), 1)
        self.assertEqual(summary.run_exit_status(unproven.as_dict(), dry_run=True), 1)

    def test_dry_run_excludes_every_payable_by_name_and_writes_nothing(self):
        index = self._index()
        self._worksheet_54839(index)
        index.payables_by_buysell[""] = [_payable("999001", "", VENDOR, "12.5", "50100", "NOREF")]
        report = ImportReport()
        native_document_import.realize(self.importer, index, report, dict(self.partner_by_cp), None, False, True)

        self.assertEqual(report.counts["transactions"]["skipped"], 1)
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_"))
        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_"))
        self.assertEqual(
            report.census["payables_excluded"],
            {"rows": 8, "amount": 14566.48, "by_reason": {"dry_run": {"rows": 8, "amount": 14566.48}}},
        )
        self.assertEqual(report.census["payables_unselected"], {"rows": 0, "amount": 0.0})
        reconciliation = report.census["payables_reconciliation"]
        # The outside-universe row is still quarantined; nothing is claimed as billed.
        self.assertEqual(reconciliation["source_rows"], 9)
        self.assertEqual((reconciliation["billed_rows"], reconciliation["quarantined_rows"]), (0, 1))
        self.assertEqual(reconciliation["excluded_rows"], 8)
        self.assertTrue(reconciliation["closes"])

    def test_blocked_sale_confirmation_is_a_rejected_transaction_that_carries_no_cost(self):
        """A linked sale order is not a transaction: until the order confirms, nothing is created or carried."""
        from unittest.mock import patch

        from odoo.exceptions import UserError

        index = self._index()
        self._worksheet_with_sale_and_costs(index, "60910", "9691", "16091", "9690", "8091", "2026-07-06 00:00:00")
        with patch.object(type(self.env["sale.order"]), "action_confirm", side_effect=UserError("blocked")):
            report = self._run(index)

        order = self._marked("sale.order", "legacy_erp_so_")
        self.assertEqual(order.state, "draft")
        self.assertFalse(self.Transaction.search([("name", "=", "60910")]))
        self.assertEqual(report.counts["transactions"], {"created": 0, "updated": 0, "skipped": 0, "rejected": 1})
        self.assertIn(
            ("BuySell", "60910", f"sale order {order.name} not confirmed (draft); no transaction compiled"),
            self._anomaly_details(report),
        )
        # The material bill is a document of its own and is still written.
        self.assertAlmostEqual(self._marked("account.move", "legacy_erp_ininv_8609101").amount_total, 400.0, places=2)
        quarantine = self._quarantine_by_id(report)
        self.assertEqual(quarantine["8609102"]["disposition"], "not_realized")
        self.assertEqual(
            quarantine["8609102"]["reason"],
            "GL 50300 has no native account in the crosswalk and no transaction exists to carry it"
            f" (sale order {order.name} not confirmed (draft))",
        )
        self.assertEqual(quarantine["8609104"]["disposition"], "not_realized")
        self.assertEqual(
            quarantine["8609104"]["reason"],
            "vendor 9999 is not an imported counterparty; no transaction exists to carry it"
            f" (sale order {order.name} not confirmed (draft))",
        )
        payables = report.census["payables"]
        self.assertEqual(payables["gl_50300_not_realized"], {"rows": 1, "worksheets": 1, "amount": 80.0})
        self.assertNotIn("gl_50300_as_other_expenses", payables)
        self.assertEqual(
            report.census["payables_reconciliation"]["by_disposition"], {"not_realized": {"rows": 2, "amount": 135.0}}
        )
        self.assertTrue(report.census["payables_reconciliation"]["closes"])

        # Once the order confirms, the transaction exists and the same rows are carried, and say so.
        second = self._run(index)
        tx = self.Transaction.search([("name", "=", "60910")])
        self.assertEqual(len(tx), 1)
        self.assertEqual(second.counts["transactions"], {"created": 1, "updated": 0, "skipped": 0, "rejected": 0})
        self.assertAlmostEqual(tx.other_expenses, 80.0, places=2)
        self.assertAlmostEqual(tx.freight_actual, 55.0, places=2)
        quarantine = self._quarantine_by_id(second)
        self.assertEqual(quarantine["8609102"]["disposition"], "transaction_only_cost")
        self.assertEqual(quarantine["8609104"]["disposition"], "transaction_only_cost")
        self.assertEqual(
            second.census["payables"]["gl_50300_as_other_expenses"], {"rows": 1, "worksheets": 1, "amount": 80.0}
        )
        self.assertTrue(second.census["payables_reconciliation"]["closes"])
        # Replay: the transaction already exists, so it is skipped, and the census is stable.
        before = self._snapshot()
        third = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(third.counts["transactions"], {"created": 0, "updated": 0, "skipped": 1, "rejected": 0})
        self.assertEqual(third.census["payables_reconciliation"], second.census["payables_reconciliation"])
        self.assertEqual(third.census["unresolved_bills"], second.census["unresolved_bills"])

    def test_failed_transaction_compile_is_a_rejected_transaction_until_it_compiles(self):
        """A confirmed order whose compile fails has no transaction: rejected, and its costs are not carried."""
        from unittest.mock import patch

        index = self._index()
        self._worksheet_54839(index)
        self._run(index)
        order = self._marked("sale.order", "legacy_erp_so_")
        self.assertEqual(order.state, "sale")
        # A second worksheet arrives on the already confirmed order; only the standalone compile can serve it.
        self._add_order(index, "6350", "7276", "PO", VENDOR)
        index.order_lines["9300"] = {"PONumber": "14263"}
        self._add_line(
            index, "9300", "14263", _line("6703", "54840", "9300", "9301", "40000", "20000", "40100", "18000")
        )
        index.order_lines["9301"] = {"PONumber": "7276"}
        index.buysells["54840"] = _buysell("54840", "2022-02-20 00:00:00")
        index.payables_by_buysell["54840"] = [
            _payable("8548401", "54840", VENDOR, "18000", "50100", "INV-54840"),
            _payable("8548402", "54840", VENDOR, "90", "50600", "EQP-54840"),
        ]
        with patch.object(
            type(self.env["sale.order"]), "_compile_worksheet_transactions", side_effect=RuntimeError("compile failed")
        ):
            report = self._run(index)

        self.assertFalse(self.Transaction.search([("name", "=", "54840")]))
        self.assertEqual(report.counts["transactions"], {"created": 0, "updated": 0, "skipped": 1, "rejected": 1})
        self.assertIn(
            ("BuySell", "54840", "sale order confirmed but no transaction was compiled; no transaction compiled"),
            self._anomaly_details(report),
        )
        self.assertAlmostEqual(self._marked("account.move", "legacy_erp_ininv_8548401").amount_total, 18000.0, places=2)
        entry = self._quarantine_by_id(report)["8548402"]
        self.assertEqual(entry["disposition"], "not_realized")
        self.assertEqual(
            entry["reason"],
            "GL 50600 has no native account in the crosswalk and no transaction exists to carry it"
            " (sale order confirmed but no transaction was compiled)",
        )
        self.assertEqual(
            report.census["payables"]["gl_50600_not_realized"], {"rows": 1, "worksheets": 1, "amount": 90.0}
        )
        self.assertTrue(report.census["payables_reconciliation"]["closes"])

        second = self._run(index)
        later = self.Transaction.search([("name", "=", "54840")])
        self.assertEqual(len(later), 1)
        self.assertAlmostEqual(later.other_expenses, 90.0, places=2)
        self.assertEqual(second.counts["transactions"], {"created": 1, "updated": 0, "skipped": 1, "rejected": 0})
        self.assertEqual(self._quarantine_by_id(second)["8548402"]["disposition"], "transaction_only_cost")
        self.assertTrue(second.census["payables_reconciliation"]["closes"])

    # ── Workstream C: weight and price fidelity ────────────────────────────
    def test_short_ton_lines_are_carried_in_pounds_at_two_thousand_per_ton(self):
        index = self._index()
        self._add_order(index, "9601", "16001", "SO", CUSTOMER, "2026-07-01 00:00:00")
        self._add_order(index, "9600", "8001", "PO", VENDOR, "2026-07-01 00:00:00")
        detail = _line("13653", "60705", "9801", "9800", "20", "1950", "20", "1840")
        detail.update({"SWeightUOM": "S", "SPrice": "97.5", "PWeightUOM": "S", "PPrice": "92"})
        self._add_line(index, "9801", "16001", detail)
        index.order_lines["9800"] = {"PONumber": "8001"}
        index.buysells["60705"] = _buysell("60705", "2026-07-01 00:00:00")
        index.payables_by_buysell["60705"] = [_payable("700001", "60705", VENDOR, "1840", "50100", "8001")]
        report = self._run(index)

        pound = self.env.ref("uom.product_uom_lb")
        tx = self.Transaction.search([("name", "=", "60705")])
        sale_line = tx.sale_order_id.order_line
        self.assertAlmostEqual(sale_line.product_uom_qty, 40000.0)
        self.assertEqual(sale_line.product_uom_id, pound)
        self.assertNotEqual(sale_line.product_uom_id, self.env.ref("uom.product_uom_ton"))
        self.assertAlmostEqual(sale_line.price_subtotal, 1950.0, places=2)
        purchase_line = tx.purchase_order_ids.order_line
        self.assertAlmostEqual(purchase_line.product_qty, 40000.0)
        self.assertEqual(purchase_line.product_uom_id, pound)
        self.assertAlmostEqual(purchase_line.price_subtotal, 1840.0, places=2)
        invoice_line = tx.customer_invoice_id.invoice_line_ids
        self.assertAlmostEqual(invoice_line.quantity, 40000.0)
        self.assertEqual(invoice_line.product_uom_id, pound)
        self.assertAlmostEqual(tx.customer_invoice_id.amount_total, 1950.0, places=2)
        bill_line = tx.vendor_bill_ids.invoice_line_ids
        self.assertAlmostEqual(bill_line.quantity, 40000.0)
        self.assertEqual(bill_line.product_uom_id, pound)
        self.assertAlmostEqual(tx.vendor_bill_ids.amount_total, 1840.0, places=2)
        self.assertEqual(report.census["price_precision"]["lines"], 0)

    def test_sub_cent_unit_price_keeps_the_source_amount_and_is_only_rounded_for_display(self):
        """``Product Price`` is a display precision: the stored unit price is unrounded and the line reproduces the amount."""
        display_digits = self.env["decimal.precision"].precision_get("Product Price")
        # ``get_digits`` is falsy (``False``) for a Float declared without ``digits``.
        self.assertFalse(self.env["account.move.line"]._fields["price_unit"].get_digits(self.env))
        self.assertFalse(self.env["sale.order.line"]._fields["price_unit"].get_digits(self.env))
        self.assertFalse(self.env["purchase.order.line"]._fields["price_unit"].get_digits(self.env))
        index = self._index()
        self._add_order(index, "9611", "16011", "SO", CUSTOMER, "2026-07-02 00:00:00")
        self._add_order(index, "9610", "8011", "PO", VENDOR, "2026-07-02 00:00:00")
        # 10,000 lb sold for 2,441.00 (0.2441/lb, four decimals) and bought for 2,000.00 (0.20/lb).
        self._add_line(
            index, "9811", "16011", _line("13700", "60710", "9811", "9810", "10000", "2441", "10000", "2000")
        )
        index.order_lines["9810"] = {"PONumber": "8011"}
        index.buysells["60710"] = _buysell("60710", "2026-07-02 00:00:00")
        index.payables_by_buysell["60710"] = [_payable("700011", "60710", VENDOR, "2000", "50100", "8011")]
        report = self._run(index)

        tx = self.Transaction.search([("name", "=", "60710")])
        sale_line = tx.sale_order_id.order_line
        self.assertAlmostEqual(sale_line.price_unit, 0.2441, places=6)
        self.assertNotAlmostEqual(sale_line.price_unit, round(0.2441, display_digits), places=4)
        self.assertAlmostEqual(sale_line.price_subtotal, 2441.0, places=2)
        self.assertAlmostEqual(tx.customer_invoice_id.invoice_line_ids.price_unit, 0.2441, places=6)
        self.assertAlmostEqual(tx.customer_invoice_id.amount_total, 2441.0, places=2)
        self.assertAlmostEqual(tx.purchase_order_ids.order_line.price_subtotal, 2000.0, places=2)
        self.assertAlmostEqual(tx.revenue_total, 2441.0, places=2)
        self.assertAlmostEqual(tx.purchase_cost_total, 2000.0, places=2)
        # Re-read from the database: the column is unrounded, not merely the cache.
        self.env.invalidate_all()
        self.assertAlmostEqual(sale_line.price_unit, 0.2441, places=6)
        precision = report.census["price_precision"]
        self.assertIsNone(precision["digits"])
        self.assertEqual(precision["quantity_digits"], self.env["decimal.precision"].precision_get("Product Unit"))
        self.assertEqual(precision["display_digits"], display_digits)
        self.assertEqual(precision["lines"], 0)
        self.assertFalse([item for item in report.anomalies if item["key"] == "13700"])

    def test_source_amount_drift_is_reported_when_a_quantity_cannot_be_stored_exactly(self):
        """A weight with more decimals than ``Product Unit`` keeps is a reported exception, not a silent change."""
        quantity_digits = self.env["decimal.precision"].precision_get("Product Unit")
        index = self._index()
        self._add_order(index, "9631", "16031", "SO", CUSTOMER, "2026-07-03 00:00:00")
        self._add_order(index, "9630", "8031", "PO", VENDOR, "2026-07-03 00:00:00")
        # 3.333 lb at 30.003/lb = 100.00: the quantity stores at two decimals, the line reads 99.99.
        self._add_line(index, "9831", "16031", _line("13710", "60730", "9831", "9830", "3.333", "100", "3.333", "100"))
        index.order_lines["9830"] = {"PONumber": "8031"}
        index.buysells["60730"] = _buysell("60730", "2026-07-03 00:00:00")
        report = self._run(index)

        tx = self.Transaction.search([("name", "=", "60730")])
        stored_quantity = round(3.333, quantity_digits)
        stored_amount = round(stored_quantity * (100.0 / 3.333), 2)
        self.assertAlmostEqual(tx.sale_order_id.order_line.product_uom_qty, stored_quantity, places=quantity_digits)
        self.assertAlmostEqual(tx.customer_invoice_id.amount_total, stored_amount, places=2)
        drift = round(stored_amount - 100.0, 2)
        precision = report.census["price_precision"]
        details = {(item["table"], item["key"], item["detail"]) for item in report.anomalies}
        if drift:
            self.assertEqual(precision["lines"], 2, "sale and purchase side of the one line")
            self.assertAlmostEqual(precision["net_drift"], 2 * drift, places=2)
            self.assertAlmostEqual(precision["max_abs_drift"], abs(drift), places=2)
            self.assertIn(
                (
                    "WKSDetail",
                    "13710",
                    f"sale amount 100.00 stored as {stored_amount:.2f} at the stored quantity and price",
                ),
                details,
            )
        else:
            self.assertEqual(precision["lines"], 0)

    # ── Workstream B: order-link exception census ──────────────────────────
    def test_worksheet_without_a_sale_link_keeps_its_purchase_documents_and_is_censused(self):
        """No sale order is manufactured; the purchase side is realized on its own identity and reported."""
        index = self._index()
        self._add_order(index, "9620", "8021", "PO", VENDOR, "2020-02-01 00:00:00")
        detail = _line("13800", "60720", "", "9820", "5000", "1500", "5000", "1000")
        self._add_line(index, "9820", "8021", detail)
        index.buysells["60720"] = _buysell("60720", "2020-02-01 00:00:00")
        index.payables_by_buysell["60720"] = [_payable("700021", "60720", VENDOR, "1000", "50100", "8021")]
        index.ledger_by_buysell["60720"] = [_ledger("7001", "60720", "B", None, None, sale="1500", cost="1000")]
        index.receipts_by_buysell["60720"] = [{"BuySellNo": "60720"}]
        # A second worksheet whose sale key points at a purchase order number.
        self._add_order(index, "9621", "8022", "PO", VENDOR, "2020-02-02 00:00:00")
        index.order_lines["9821"] = {"PONumber": "8022"}
        self._add_line(index, "9822", "8022", _line("13801", "60721", "9821", "9822", "100", "50", "100", "40"))
        index.buysells["60721"] = _buysell("60721", "2020-02-02 00:00:00")
        report = self._run(index)

        self.assertFalse(self.Transaction.search([("name", "in", ["60720", "60721"])]))
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_"))
        self.assertFalse(self._marked("account.move", "legacy_erp_outinv_"))
        purchases = self._marked("purchase.order", "legacy_erp_po_")
        self.assertEqual(sorted(purchases.mapped("name")), ["8021", "8022"])
        bill = self._marked("account.move", "legacy_erp_ininv_700021")
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertAlmostEqual(bill.amount_total, 1000.0, places=2)
        # No transaction exists for either worksheet, so neither is a created transaction.
        self.assertEqual(report.counts["transactions"]["created"], 0)
        self.assertEqual(report.counts["transactions"]["skipped"], 0)
        self.assertEqual(report.counts["transactions"]["rejected"], 2)
        self.assertEqual(report.counts["transaction_lines"]["created"], 2, "the purchase-side lines were written")
        self.assertEqual(report.census["payables_reconciliation"]["billed_rows"], 1)
        self.assertTrue(report.census["payables_reconciliation"]["closes"])
        details = {(item["table"], item["key"], item["detail"]) for item in report.anomalies}
        self.assertIn(("WKSDetail", "13800", "sale link: blank line key"), details)
        self.assertIn(("WKSDetail", "13801", "sale link: SO 8022 matched 0 headers (exists as PO)"), details)
        for number in ("60720", "60721"):
            self.assertIn(
                ("BuySell", number, "no sale order link: purchase documents realized, no transaction compiled"),
                details,
            )

        by_reason = {(g["side"], g["reason"]): g for g in report.census["lines_by_reason"]}
        self.assertEqual(by_reason[("sale", "blank_key")]["lines"], 1)
        self.assertEqual(by_reason[("sale", "blank_key")]["sale_amount"], 1500.0)
        self.assertEqual(by_reason[("sale", "number_under_other_source")]["lines"], 1)
        self.assertEqual(by_reason[("sale", "number_under_other_source")]["distinct_keys"], 1)
        self.assertNotIn(("purchase", "blank_key"), by_reason)
        unsold = report.census["worksheets"]["without_sale_link"]
        self.assertEqual(unsold["worksheets"], 2)
        self.assertEqual(unsold["numbers"], ["60720", "60721"])
        self.assertEqual(unsold["with_purchase_link"], 2)
        self.assertEqual(unsold["with_customer_trade_ledger"], 1)
        self.assertEqual(unsold["with_customer_receipts"], 1)
        self.assertEqual(unsold["with_payables"], 1)
        self.assertEqual(unsold["partner_active"], 2)
        self.assertEqual(unsold["sale_amount"], 1550.0)
        self.assertEqual(unsold["purchase_amount"], 1040.0)
        self.assertEqual(unsold["years"], {"2020": 2})
        self.assertEqual(report.census["worksheets"]["without_purchase_link"]["worksheets"], 0)

        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(replay.counts["transactions"]["created"], 0)
        self.assertEqual(replay.counts["transactions"]["rejected"], 2, "a replay reports the same outcome")
        self.assertEqual(replay.counts["transaction_lines"]["created"], 0)
        self.assertEqual(replay.census["worksheets"]["without_sale_link"]["worksheets"], 2)
        self.assertTrue(replay.census["payables_reconciliation"]["closes"])

    def test_worksheet_53797_nets_to_zero_revenue_and_negative_margin(self):
        index = self._index()
        self._add_order(index, "7001", "13289", "SO", OTHER_CUSTOMER, "2021-09-01 00:00:00")
        self._add_order(index, "7000", "6240", "PO", VENDOR, "2021-09-01 00:00:00")
        self._add_line(index, "6683", "13289", _line("5194", "53797", "6683", "6460", "200", "2000", "200", "2000"))
        index.order_lines["6460"] = {"PONumber": "6240"}
        index.buysells["53797"] = _buysell("53797", "2021-09-01 00:00:00", cust=OTHER_CUSTOMER)
        index.payables_by_buysell["53797"] = [_payable("562145", "53797", VENDOR, "2000", "50100", "6240")]
        index.ledger_by_buysell["53797"] = [
            _ledger("4669", "53797", "B", None, None, sale="2000", cost="2000"),
            _ledger(
                "4670", "53797", "A", "S", "Y", sale="-2000", cp_id=OTHER_CUSTOMER, memo="CM 53797", title="CREDIT MEMO"
            ),
        ]
        self._run(index)

        tx = self.Transaction.search([("name", "=", "53797")])
        self.assertEqual(len(tx), 1)
        self.assertAlmostEqual(tx.customer_invoice_id.amount_total, 2000.0, places=2)
        credit = self._marked("account.move", "legacy_erp_ledger_4670")
        self.assertAlmostEqual(credit.amount_total, 2000.0, places=2)
        self.assertEqual(credit.move_type, "out_refund")
        self.assertAlmostEqual(tx.revenue_total, 0.0, places=2)
        self.assertAlmostEqual(tx.purchase_cost_total, 2000.0, places=2)
        self.assertAlmostEqual(tx.gross_margin, -2000.0, places=2)

    # ── F4: worksheet is the transaction; orders may be shared ─────────────
    def test_two_worksheets_on_one_sale_order_compile_two_transactions_and_replay_adds_nothing(self):
        index = self._index()
        self._worksheet_54839(index)
        # Worksheet 54840 ships a second line of SO 14263 against its own PO 7276.
        self._add_order(index, "6350", "7276", "PO", VENDOR)
        index.order_lines["9300"] = {"PONumber": "14263"}
        index.order_lines["9301"] = {"PONumber": "7276"}
        self._add_line(
            index, "9300", "14263", _line("6703", "54840", "9300", "9301", "40000", "20000", "40100", "18000")
        )
        index.order_lines["9301"] = {"PONumber": "7276"}
        index.buysells["54840"] = _buysell("54840", "2022-02-20 00:00:00")
        index.payables_by_buysell["54840"] = [_payable("595000", "54840", VENDOR, "18000", "50100", "7276")]

        self._run(index)

        sales = self._marked("sale.order", "legacy_erp_so_")
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales.origin, "54839, 54840")
        self.assertEqual(len(sales.order_line), 2)
        purchases = self._marked("purchase.order", "legacy_erp_po_")
        self.assertEqual(sorted(purchases.mapped("name")), ["7275", "7276"])
        transactions = self.Transaction.search([("name", "in", ["54839", "54840"])], order="name")
        self.assertEqual(transactions.mapped("name"), ["54839", "54840"])
        self.assertEqual(set(transactions.mapped("sale_order_id").ids), {sales.id})
        by_name = {tx.name: tx for tx in transactions}
        self.assertEqual(by_name["54839"].purchase_order_ids.mapped("name"), ["7275"])
        self.assertEqual(by_name["54840"].purchase_order_ids.mapped("name"), ["7276"])
        self.assertEqual(by_name["54839"].customer_invoice_id.invoice_origin, "54839")
        self.assertEqual(by_name["54840"].customer_invoice_id.invoice_origin, "54840")
        self.assertEqual(by_name["54840"].vendor_bill_ids.mapped("ref"), ["7276"])
        self.assertFalse(self.Transaction.search([("name", "like", "54839-"), ("name", "!=", "54839")]))

        before = self._snapshot()
        report = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(report.counts["transactions"]["created"], 0)
        self.assertEqual(report.counts["transactions"]["skipped"], 2)
        self.assertEqual(report.counts["transaction_lines"]["created"], 0)

    def test_two_worksheets_on_one_order_across_commit_batches(self):
        """The second worksheet arrives after its order was already confirmed."""
        index = self._index()
        self._worksheet_54839(index)
        self._run(index)
        self.assertEqual(self._marked("sale.order", "legacy_erp_so_").state, "sale")

        self._add_order(index, "6350", "7276", "PO", VENDOR)
        index.order_lines["9300"] = {"PONumber": "14263"}
        index.order_lines["9301"] = {"PONumber": "7276"}
        self._add_line(
            index, "9300", "14263", _line("6703", "54840", "9300", "9301", "40000", "20000", "40100", "18000")
        )
        index.order_lines["9301"] = {"PONumber": "7276"}
        index.buysells["54840"] = _buysell("54840", "2022-02-20 00:00:00")
        self._run(index)

        sales = self._marked("sale.order", "legacy_erp_so_")
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales.origin, "54839, 54840")
        later = self.Transaction.search([("name", "=", "54840")])
        self.assertEqual(len(later), 1)
        self.assertEqual(later.sale_order_id, sales)
        self.assertEqual(later.purchase_order_ids.mapped("name"), ["7276"])
        self.assertEqual(self.Transaction.search_count([("name", "in", ["54839", "54840"])]), 2)

    def test_blank_ppo_id_links_the_purchase_order_named_on_the_worksheet(self):
        """PPo is the purchase-order number when the line key does not resolve."""
        index = self._index()
        number = "60821"
        self._add_order(index, "18980", "18979", "SO", CUSTOMER, "2024-09-01 00:00:00")
        self._add_order(index, "18981", "7275", "PO", VENDOR, "2024-09-01 00:00:00")
        detail = _line("160821", number, "18980", "", "1000", "500", "1000", "400")
        detail["PPo"] = "7275"
        index.order_lines["18980"] = {"PONumber": "18979"}
        index.lines[detail["DetailID"]] = detail
        index.lines_by_buysell[number] = [detail["DetailID"]]
        index.buysells[number] = _buysell(number, "2024-09-01 00:00:00")
        report = self._run(index)

        tx = self.Transaction.search([("name", "=", number)])
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx.sale_order_id.name, "18979")
        self.assertEqual(tx.purchase_order_ids.mapped("name"), ["7275"])
        self.assertEqual(tx.supplier_id, self.vendor)
        self.assertNotIn(("WKSDetail", "160821", "purchase link: blank line key"), self._anomaly_details(report))

    def test_replay_links_a_purchase_order_onto_the_existing_transaction(self):
        """A worksheet imported before its purchase order keeps that row and gains the order."""
        index = self._index()
        number = "60822"
        self._add_order(index, "18990", "18990", "SO", CUSTOMER, "2024-09-02 00:00:00")
        detail = _line("160822", number, "18990", "", "1000", "500", "1000", "400")
        index.order_lines["18990"] = {"PONumber": "18990"}
        index.lines[detail["DetailID"]] = detail
        index.lines_by_buysell[number] = [detail["DetailID"]]
        index.buysells[number] = _buysell(number, "2024-09-02 00:00:00")
        self._run(index)

        tx = self.Transaction.search([("name", "=", number)])
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx.state, "closed")
        self.assertFalse(tx.purchase_order_ids)
        sale_id = tx.sale_order_id.id

        self._add_order(index, "18991", "7278", "PO", VENDOR, "2024-09-02 00:00:00")
        detail["PPo"] = "7278"
        self._run(index)

        tx.invalidate_recordset()
        self.assertEqual(self.Transaction.search_count([("name", "=", number)]), 1)
        self.assertEqual(tx.state, "closed")
        self.assertEqual(tx.sale_order_id.id, sale_id)
        self.assertEqual(tx.purchase_order_ids.mapped("name"), ["7278"])
        self.assertEqual(tx.supplier_id, self.vendor)

    def test_worksheet_with_two_sale_orders_compiles_one_transaction(self):
        index = self._index()
        self._add_order(index, "8001", "15001", "SO", CUSTOMER)
        self._add_order(index, "8002", "15002", "SO", CUSTOMER)
        self._add_order(index, "8000", "7300", "PO", VENDOR)
        index.order_lines["9400"] = {"PONumber": "15001"}
        index.order_lines["9401"] = {"PONumber": "15002"}
        index.order_lines["9402"] = {"PONumber": "7300"}
        self._add_line(index, "9400", "15001", _line("7001", "57135", "9400", "9402", "10000", "5000", "10000", "4000"))
        self._add_line(index, "9401", "15002", _line("7002", "57135", "9401", "9402", "10000", "5000", "10000", "4000"))
        index.order_lines["9402"] = {"PONumber": "7300"}
        index.buysells["57135"] = _buysell("57135", "2024-03-01 00:00:00")
        report = self._run(index)

        transactions = self.Transaction.search([("name", "like", "57135")])
        self.assertEqual(transactions.mapped("name"), ["57135"])
        sales = self._marked("sale.order", "legacy_erp_so_")
        self.assertEqual(len(sales), 2)
        self.assertEqual(transactions.sale_order_id, sales.sorted("id")[0])
        self.assertEqual(transactions.purchase_order_ids.mapped("name"), ["7300"])
        other = sales.sorted("id")[1]
        self.assertFalse(other.transaction_id)
        notes = transactions.message_ids.filtered(lambda message: "also carries sale order" in (message.body or ""))
        self.assertTrue(notes)
        self.assertIn(other.name, notes[0].body)
        self.assertIn(
            ("BuySell", "57135", "worksheet carries 2 sale orders"),
            {(a["table"], a["key"], a["detail"]) for a in report.anomalies},
        )
        invoice = self._marked("account.move", "legacy_erp_outinv_")
        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.partner_id, self.customer)
        self.assertEqual(len(invoice.invoice_line_ids), 2)

    def test_worksheet_whose_sale_orders_have_different_customers_is_rejected(self):
        """One worksheet carries one customer invoice; two customers cannot share it."""
        index = self._index()
        self._add_order(index, "8001", "15001", "SO", CUSTOMER)
        self._add_order(index, "8002", "15002", "SO", OTHER_CUSTOMER)
        self._add_order(index, "8000", "7300", "PO", VENDOR)
        index.order_lines["9400"] = {"PONumber": "15001"}
        index.order_lines["9401"] = {"PONumber": "15002"}
        index.order_lines["9402"] = {"PONumber": "7300"}
        self._add_line(index, "9400", "15001", _line("7001", "57136", "9400", "9402", "10000", "5000", "10000", "4000"))
        self._add_line(index, "9401", "15002", _line("7002", "57136", "9401", "9402", "10000", "5000", "10000", "4000"))
        index.buysells["57136"] = _buysell("57136", "2024-03-01 00:00:00")
        report = self._run(index)

        self.assertFalse(self.Transaction.search([("name", "=", "57136")]))
        self.assertFalse(self._marked("account.move", "legacy_erp_outinv_"))
        self.assertEqual(report.counts["transactions"]["rejected"], 1)
        self.assertIn(
            ("BuySell", "57136", "ValueError"), {(a["table"], a["key"], a["detail"]) for a in report.anomalies}
        )

    def test_rejected_worksheet_does_not_poison_the_product_cache(self):
        """A product created by a worksheet that is then rolled back must be recreated for the next worksheet."""
        index = self._index()
        # Worksheet 58001: vendor 9999 is not an imported counterparty, so the worksheet is rejected
        # after its (new-grade) sale line created the product inside the rolled-back savepoint.
        self._add_order(index, "8101", "15101", "SO", CUSTOMER)
        self._add_order(index, "8100", "7400", "PO", "9999")
        self._add_line(
            index,
            "9500",
            "15101",
            _line("7101", "58001", "9500", "9501", "1000", "500", "1000", "400", grade="NEW-GRADE"),
        )
        index.order_lines["9501"] = {"PONumber": "7400"}
        index.buysells["58001"] = _buysell("58001", "2024-03-01 00:00:00", vendor="9999")
        # Worksheet 58002: same grade, every counterparty active.
        self._add_order(index, "8103", "15102", "SO", CUSTOMER)
        self._add_order(index, "8102", "7401", "PO", VENDOR)
        self._add_line(
            index,
            "9502",
            "15102",
            _line("7102", "58002", "9502", "9503", "1000", "500", "1000", "400", grade="NEW-GRADE"),
        )
        index.order_lines["9503"] = {"PONumber": "7401"}
        index.buysells["58002"] = _buysell("58002", "2024-03-02 00:00:00")
        report = self._run(index)

        self.assertEqual(self.Transaction.search([("name", "in", ["58001", "58002"])]).mapped("name"), ["58002"])
        self.assertIn(("BuySell", "58001"), {(a["table"], a["key"]) for a in report.anomalies})
        products = self._marked("product.product", "legacy_erp_grade_NEW")
        self.assertEqual(len(products), 1)
        self.assertEqual(
            self.env["sale.order.line"].search([("product_id", "=", products.id)]).order_id.origin, "58002"
        )

    # ── F6: commission recipient and cutoff ─────────────────────────────────
    def _commission_worksheet(self, index, number, order_dt, **slots):
        so_poid, po_poid = f"9{number}", f"8{number}"
        self._add_order(index, so_poid, f"S{number}", "SO", CUSTOMER, order_dt)
        self._add_order(index, po_poid, f"P{number}", "PO", VENDOR, order_dt)
        index.order_lines[f"L{so_poid}"] = {"PONumber": f"S{number}"}
        index.order_lines[f"L{po_poid}"] = {"PONumber": f"P{number}"}
        self._add_line(
            index,
            f"L{so_poid}",
            f"S{number}",
            _line(f"D{number}", number, f"L{so_poid}", f"L{po_poid}", "1000", "500", "1000", "400"),
        )
        index.order_lines[f"L{po_poid}"] = {"PONumber": f"P{number}"}
        index.buysells[number] = _buysell(number, order_dt, **slots)

    def test_commission_recipient_amount_and_cutoff_per_slot(self):
        index = self._index()
        self._commission_worksheet(index, "60001", "2022-01-05 00:00:00")
        self._commission_worksheet(index, "60002", "2022-01-05 00:00:00", ReferrerNo2="TF", Commission2="168.28")
        self._commission_worksheet(
            index,
            "60003",
            "2021-04-01 00:00:00",
            ReferrerNo1="GS",
            Commission1="389.19",
            ReferrerNo2="TF",
            Commission2="50",
        )
        self._commission_worksheet(index, "60004", "2026-05-31 00:00:00", ReferrerNo1="TF", Commission1="10")
        self._commission_worksheet(index, "60005", "2026-06-01 00:00:00", ReferrerNo1="TF", Commission1="10")
        self._commission_worksheet(
            index,
            "60006",
            "2022-01-05 00:00:00",
            ReferrerNo1="IB",
            Commission1="0",
            ReferrerNo2="TF",
            Commission2="75.5",
        )
        report = self._run(index)
        tx = {
            t.name: t
            for t in self.Transaction.search([("name", "in", ["60001", "60002", "60003", "60004", "60005", "60006"])])
        }
        self.assertEqual(len(tx), 6)

        self.assertFalse(tx["60001"].user_id)
        self.assertEqual(tx["60002"].user_id, self.rep_tf)
        self.assertEqual(tx["60002"].sale_order_id.user_id, self.rep_tf)
        self.assertEqual(tx["60002"].purchase_order_ids.user_id, self.rep_tf)
        self.assertFalse(
            tx["60003"].user_id, "slot 1 recipient GS is historical and has no user; nobody is substituted"
        )
        self.assertEqual(tx["60006"].user_id, self.rep_tf, "the paid slot is the recipient, not the unpaid slot 1 name")
        anomalies = {(a["key"], a["detail"]) for a in report.anomalies}
        self.assertIn(("60003", "two commission recipients: GS, TF"), anomalies)
        self.assertIn(("60003", "commission recipient GS has no user"), anomalies)
        slot_notes = tx["60003"].message_ids.filtered(lambda m: "Commission slots" in (m.body or ""))
        self.assertTrue(slot_notes)
        self.assertIn("slot 1 GS 389.19", slot_notes[0].body)
        self.assertIn("slot 2 TF 50.00", slot_notes[0].body)

        if "commission_locked" not in self.Transaction._fields:
            return
        self.assertTrue(all(t.commission_locked for t in tx.values()))
        self.assertAlmostEqual(tx["60001"].commission_locked_amount, 0.0)
        self.assertAlmostEqual(tx["60002"].commission_locked_amount, 168.28)
        self.assertAlmostEqual(tx["60003"].commission_locked_amount, 439.19)
        self.assertAlmostEqual(tx["60006"].commission_locked_amount, 75.5)
        self.assertFalse(tx["60002"].commission_payout_state)
        self.assertFalse(tx["60004"].commission_payout_state, "Historic payment was not proved by date")
        self.assertFalse(tx["60005"].commission_payout_state, "Historic payment was not proved by date")
        self.assertTrue(all(t.legacy_erp_history for t in tx.values()))
        self.assertEqual(tx["60002"].sale_order_id.date_order.date(), date(2022, 1, 5))
        # The payout model is in the dependent commission addon. Neither the
        # historical date nor the source amount proves payment or liability.
        self.assertTrue(all(not t.commission_payout_state for t in tx.values()))

    def test_native_import_normalizes_materials_and_replays(self):
        """Source-index rows go through realize and the shared normalizer."""
        from odoo.addons.plasticos_material_profile.models import material_normalizer

        index = self._index()
        number = "60706"
        self._add_order(index, "9602", "16002", "SO", CUSTOMER, "2026-07-02 00:00:00")
        self._add_order(index, "9603", "8002", "PO", VENDOR, "2026-07-02 00:00:00")
        details = [
            ("13610", "GRADE-SHARED", "99 Clear LDPE Film"),
            ("13611", "GRADE-SHARED", "90 Clear LDPE Film"),
            ("13612", "GRADE-SHARED", "HDPE Drums"),
            ("13613", "GRADE-UNKNOWN", "mystery fluff"),
        ]
        for detail_id, grade, description in details:
            detail = _line(detail_id, number, "9802", "9803", "1000", "100", "1000", "80", grade)
            detail["InvoiceDesc"] = description
            index.lines[detail_id] = detail
            index.lines_by_buysell.setdefault(number, []).append(detail_id)
        index.order_lines["9802"] = {"PONumber": "16002"}
        index.order_lines["9803"] = {"PONumber": "8002"}
        index.buysells[number] = _buysell(number, "2026-07-02 00:00:00")
        index.payables_by_buysell[number] = [_payable("700106", number, VENDOR, "320", "50100", "8002")]
        calls = []
        original = material_normalizer.normalize_material

        def wrapped(env, description, grade_evidence=None, structured=None):
            calls.append(description)
            return original(env, description, grade_evidence=grade_evidence, structured=structured)

        profiles = self.env["plasticos.material.profile"].search_count([])
        with patch.object(material_normalizer, "normalize_material", wrapped):
            self._run(index)
        self.assertIn("99 Clear LDPE Film", calls)
        self.assertIn("HDPE Drums", calls)
        self.assertIn("mystery fluff", calls)
        self.assertEqual(self.env["plasticos.material.profile"].search_count([]), profiles)

        sale = self._order("sale.order", "legacy_erp_so_16002")
        purchase = self._order("purchase.order.line", "legacy_erp_pol_13610")
        lines = {line.name: line for line in sale.order_line}
        grade_a = lines["99 Clear LDPE Film"]
        grade_c = lines["90 Clear LDPE Film"]
        drums = lines["HDPE Drums"]
        unknown = lines["mystery fluff"]
        self.assertEqual(grade_a.product_id.default_code, "GRADE-SHARED")
        self.assertEqual(grade_a.product_id.product_tmpl_id.polymer_id.code, "LDPE")
        self.assertEqual(grade_a.form_id.code, "FILM")
        self.assertFalse(grade_a.source_type_id)
        self.assertEqual(set(grade_a.material_attribute_ids.mapped("code")), {"clean", "dry"})
        self.assertAlmostEqual(grade_a.price_subtotal, 100.0, places=2)
        self.assertEqual(grade_c.product_id, grade_a.product_id)
        self.assertEqual(grade_c.name, "90 Clear LDPE Film")
        self.assertEqual(grade_c.form_id.code, "FILM")
        self.assertFalse(grade_c.material_attribute_ids)
        self.assertEqual(drums.product_id.default_code, "GRADE-SHARED")
        self.assertNotEqual(drums.product_id, grade_a.product_id)
        self.assertEqual(drums.product_id.product_tmpl_id.polymer_id.code, "HDPE")
        self.assertEqual(drums.material_grade_id.code, "DRUMS")
        self.assertFalse(drums.material_attribute_ids)
        self.assertFalse(unknown.product_id.product_tmpl_id.polymer_id)
        self.assertEqual(unknown.product_id.default_code, "GRADE-UNKNOWN")
        self.assertEqual(unknown.name, "mystery fluff")
        self.assertFalse(unknown.form_id)
        self.assertFalse(unknown.material_attribute_ids)
        self.assertEqual(purchase.form_id.code, "FILM")
        self.assertEqual(set(purchase.material_attribute_ids.mapped("code")), {"clean", "dry"})
        self.assertAlmostEqual(purchase.price_subtotal, 80.0, places=2)
        self.assertEqual(len(self.Transaction.search([("name", "=", number)])), 1)
        self.assertEqual(len(self._marked("sale.order.line", "legacy_erp_sol_1361")), 4)
        self.assertEqual(len(self._marked("product.product", "legacy_erp_grade_GRADE_")), 3)

        sale_ids = sale.order_line.ids
        kept = set(grade_a.material_attribute_ids.ids)
        self._run(index)
        sale = self._order("sale.order", "legacy_erp_so_16002")
        self.assertEqual(sale.order_line.ids, sale_ids)
        replayed = sale.order_line.filtered(lambda line: line.name == "99 Clear LDPE Film")
        self.assertEqual(set(replayed.material_attribute_ids.ids), kept)
        self.assertFalse(
            sale.order_line.filtered(lambda line: line.name == "90 Clear LDPE Film").material_attribute_ids
        )
        self.assertEqual(len(self._marked("sale.order.line", "legacy_erp_sol_1361")), 4)
        self.assertEqual(len(self._marked("product.product", "legacy_erp_grade_GRADE_")), 3)
        self.assertEqual(len(self.Transaction.search([("name", "=", number)])), 1)

    def test_grade_id_does_not_classify_or_contaminate_a_shared_product(self):
        """GradeID PE is product identity. It is not HDPE evidence and not a shared polymer."""
        from odoo.addons.plasticos_material_profile.models import material_normalizer

        index = self._index()
        number = "60707"
        self._add_order(index, "9604", "16003", "SO", CUSTOMER, "2026-07-03 00:00:00")
        self._add_order(index, "9605", "8003", "PO", VENDOR, "2026-07-03 00:00:00")
        details = [
            ("13620", "PE", "99 Clear LDPE Film"),
            ("13621", "PE", "mystery fluff"),
        ]
        for detail_id, grade, description in details:
            detail = _line(detail_id, number, "9804", "9805", "1000", "100", "1000", "80", grade)
            detail["InvoiceDesc"] = description
            index.lines[detail_id] = detail
            index.lines_by_buysell.setdefault(number, []).append(detail_id)
        index.order_lines["9804"] = {"PONumber": "16003"}
        index.order_lines["9805"] = {"PONumber": "8003"}
        index.buysells[number] = _buysell(number, "2026-07-03 00:00:00")
        evidence = []
        original = material_normalizer.normalize_material

        def wrapped(env, description, grade_evidence=None, structured=None):
            evidence.append(grade_evidence)
            return original(env, description, grade_evidence=grade_evidence, structured=structured)

        with patch.object(material_normalizer, "normalize_material", wrapped):
            self._run(index)
        self.assertTrue(evidence)
        self.assertTrue(all(item is None for item in evidence))
        sale = self._order("sale.order", "legacy_erp_so_16003")
        lines = {line.name: line for line in sale.order_line}
        classified = lines["99 Clear LDPE Film"]
        unresolved = lines["mystery fluff"]
        self.assertEqual(classified.product_id.default_code, "PE")
        self.assertEqual(classified.product_id.product_tmpl_id.polymer_id.code, "LDPE")
        self.assertNotEqual(classified.product_id.product_tmpl_id.polymer_id.code, "HDPE")
        self.assertEqual(classified.form_id.code, "FILM")
        self.assertFalse(unresolved.product_id.product_tmpl_id.polymer_id)
        self.assertNotEqual(unresolved.product_id, classified.product_id)
        self.assertEqual(unresolved.product_id.default_code, "PE")
        self.assertFalse(unresolved.form_id)
        self.assertEqual(len(self._marked("product.product", "legacy_erp_grade_PE")), 2)
        sale_ids = sale.order_line.ids
        product_ids = {classified.product_id.id, unresolved.product_id.id}
        self._run(index)
        sale = self._order("sale.order", "legacy_erp_so_16003")
        self.assertEqual(sale.order_line.ids, sale_ids)
        replayed = {line.name: line for line in sale.order_line}
        self.assertEqual(replayed["99 Clear LDPE Film"].product_id.product_tmpl_id.polymer_id.code, "LDPE")
        self.assertFalse(replayed["mystery fluff"].product_id.product_tmpl_id.polymer_id)
        self.assertEqual(
            {replayed["99 Clear LDPE Film"].product_id.id, replayed["mystery fluff"].product_id.id},
            product_ids,
        )
        self.assertEqual(len(self._marked("product.product", "legacy_erp_grade_PE")), 2)

    def test_inventory_inbound_keeps_the_purchase_and_the_selected_site_without_a_sale(self):
        """(INV) is a draft receipt at the ShipToID site. Outbound and ordinary sales stay on the sale path."""
        partner = self.env["res.partner"]
        jei = partner.create({"name": "JEI INC", "is_company": True, "supplier_rank": 1})
        vendor_1292 = partner.create({"name": "Vendor 1292", "is_company": True, "supplier_rank": 1})
        self.partner_by_cp["2106"] = jei.id
        self.partner_by_cp["1292"] = vendor_1292.id
        purchase = self.env["purchase.order"].with_context(tracking_disable=True, mail_create_nolog=True)
        existing_po = purchase.create({"partner_id": self.vendor.id, "name": "99901", "origin": "preexisting"})
        self.importer._write_identity_marker(purchase, "legacy_erp_po_99901", existing_po)
        index = erp_source_index.build_source_index(
            SourcePayload(
                kind=PayloadKind.GRID,
                root=Path("."),
                tables={
                    "Address": [
                        {
                            "AddressID": "404812",
                            "CpID": "(INV)",
                            "Type": "GREENVIEW WASHINGTON WAREHOUSE",
                        },
                        {"AddressID": "405026", "CpID": "(INV)", "Type": "JEI DALLAS WAREHOUSE"},
                        {"AddressID": "404999", "CpID": "(INV)", "Type": "CANCELLED ONLY"},
                    ],
                },
            )
        )
        self._add_order(index, "15168", "33498", "PO", "2106", "2026-01-15 00:00:00")
        self._add_line(index, "19339", "33498", _line("13303", "60403", "", "19339", "38580", "0", "38580", "1000"))
        index.buysells["60403"] = _buysell(
            "60403",
            "2026-01-15 00:00:00",
            cust="(INV)",
            vendor="2106",
            ShipToID="GREENVIEW WASHINGTON WAREHOUSE",
        )
        index.payables_by_buysell["60403"] = [_payable("80060403", "60403", "2106", "1000", "50100", "33498")]
        self._add_order(index, "16600", "10442", "PO", "1292", "2025-11-01 00:00:00")
        self._add_line(index, "16639", "10442", _line("12001", "58868", "", "16639", "1000", "0", "1000", "400"))
        index.buysells["58868"] = _buysell(
            "58868", "2025-11-01 00:00:00", cust="(INV)", vendor="1292", ShipToID="JEI DALLAS WAREHOUSE"
        )
        index.lines["12002"] = _line("12002", "58975", "", "", "500", "0", "500", "0")
        index.lines_by_buysell["58975"] = ["12002"]
        index.buysells["58975"] = _buysell(
            "58975", "2025-12-01 00:00:00", cust="(INV)", vendor="1292", ShipToID="JEI DALLAS WAREHOUSE"
        )
        index.payables_by_buysell["58975"] = [_payable("80058975", "58975", "1292", "10", "50100", "")]
        self._add_order(index, "18000", "99901", "PO", "2106", "2024-01-01 00:00:00")
        self._add_line(index, "18001", "99901", _line("13001", "59100", "", "18001", "10", "0", "10", "5"))
        index.buysells["59100"] = _buysell(
            "59100", "2024-01-01 00:00:00", cust="(INV)", vendor="2106", status="X", ShipToID="CANCELLED ONLY"
        )
        self._add_order(index, "19000", "33500", "PO", "2106", "2026-02-01 00:00:00")
        self._add_line(index, "19001", "33500", _line("13002", "60499", "", "19001", "20", "0", "20", "8"))
        index.buysells["60499"] = _buysell("60499", "2026-02-01 00:00:00", cust="(INV)", vendor="2106", ShipToID="")
        self._add_order(index, "20001", "17001", "SO", CUSTOMER, "2026-03-01 00:00:00")
        self._add_order(index, "20000", "9001", "PO", VENDOR, "2026-03-01 00:00:00")
        self._add_line(index, "20011", "17001", _line("14001", "61000", "20011", "20010", "100", "50", "100", "40"))
        index.order_lines["20010"] = {"PONumber": "9001"}
        index.buysells["61000"] = _buysell("61000", "2026-03-01 00:00:00", cust=CUSTOMER, vendor="(INV)")
        self._add_order(index, "21001", "17002", "SO", CUSTOMER, "2026-03-02 00:00:00")
        self._add_order(index, "21000", "9002", "PO", VENDOR, "2026-03-02 00:00:00")
        self._add_line(index, "21011", "17002", _line("14002", "61001", "21011", "21010", "80", "40", "80", "30"))
        index.order_lines["21010"] = {"PONumber": "9002"}
        index.buysells["61001"] = _buysell("61001", "2026-03-02 00:00:00")

        on_hand = self._on_hand()
        report = self._run(index)

        inbound = report.census["inventory_inbound"]
        recognized = {row["number"]: row for row in inbound["recognized"]}
        self.assertEqual(set(recognized), {"58868", "60403"})
        self.assertEqual(recognized["60403"]["address_id"], "404812")
        self.assertEqual(recognized["60403"]["location_xmlid"], "legacy_erp_inv_addr_404812")
        self.assertEqual(recognized["58868"]["address_id"], "405026")
        self.assertEqual(recognized["58868"]["location_xmlid"], "legacy_erp_inv_addr_405026")
        held_purchase = inbound["held_missing_purchase"]
        self.assertEqual([row["number"] for row in held_purchase], ["58975"])
        self.assertEqual(held_purchase[0]["address_id"], "405026")
        self.assertEqual([row["number"] for row in inbound["held_missing_destination"]], ["60499"])
        self.assertEqual(inbound["held_missing_destination"][0]["location_xmlid"], "")
        self.assertEqual([row["number"] for row in inbound["cancelled"]], ["59100"])
        self.assertEqual(inbound["cancelled"][0]["address_id"], "")
        greenview = self._order("stock.location", "legacy_erp_inv_addr_404812")
        dallas = self._order("stock.location", "legacy_erp_inv_addr_405026")
        self.assertEqual(greenview.name, "GREENVIEW WASHINGTON WAREHOUSE")
        self.assertEqual(greenview.usage, "internal")
        self.assertEqual(dallas.name, "JEI DALLAS WAREHOUSE")
        self.assertEqual(self._order("stock.location", "legacy_erp_inv_wks_60403"), greenview)
        self.assertEqual(self._order("stock.location", "legacy_erp_inv_wks_58868"), dallas)
        self.assertEqual(self._order("stock.location", "legacy_erp_inv_wks_58975"), dallas)
        self.assertFalse(self._marked("stock.location", "legacy_erp_inv_addr_404999"))
        self.assertFalse(self._marked("stock.location", "legacy_erp_inv_wks_59100"))
        self.assertFalse(self._marked("stock.location", "legacy_erp_inv_wks_60499"))
        receipt = self._order("purchase.order", "legacy_erp_po_33498")
        self.assertEqual(receipt.name, "33498")
        self.assertEqual(receipt.partner_id, jei)
        self.assertEqual(receipt.state, "draft")
        self.assertFalse(receipt.picking_ids)
        self.assertAlmostEqual(receipt.order_line.product_qty, 38580.0)
        dallas_po = self._order("purchase.order", "legacy_erp_po_10442")
        held_po = self._order("purchase.order", "legacy_erp_po_33500")
        inbound_lines = receipt.order_line | dallas_po.order_line | held_po.order_line
        self.assertFalse(self.env["stock.move"].search([("purchase_line_id", "in", inbound_lines.ids)]))
        self.assertFalse(receipt.picking_ids | dallas_po.picking_ids | held_po.picking_ids)
        self.assertEqual(dallas_po.partner_id, vendor_1292)
        self.assertNotEqual(dallas_po.id, receipt.id)
        self.assertFalse(self._marked("purchase.order", "legacy_erp_po_58975"))
        self.assertEqual(existing_po.order_line.ids, [])
        self.assertEqual(existing_po.origin, "preexisting")
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_33498"))
        self.assertFalse(self._marked("account.move", "legacy_erp_outinv_60403"))
        self.assertFalse(self.Transaction.search([("name", "in", ["60403", "58868", "58975", "59100", "60499"])]))
        bill = self._marked("account.move", "legacy_erp_ininv_80060403")
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(bill.state, "draft")
        self.assertEqual(report.counts["transactions"], {"created": 2, "updated": 0, "skipped": 2, "rejected": 3})
        details = {(item["table"], item["key"], item["detail"]) for item in report.anomalies}
        for number in ("60403", "58868", "58975", "59100", "60499"):
            self.assertNotIn(
                ("BuySell", number, "no sale order link: purchase documents realized, no transaction compiled"),
                details,
            )
        self.assertIn(("BuySell", "58975", "inventory inbound held: missing purchase"), details)
        self.assertIn(("BuySell", "60499", "inventory inbound held: missing destination"), details)
        self.assertIn(("BuySell", "59100", "inventory inbound cancelled"), details)
        self.assertEqual(report.census["worksheets"]["without_sale_link"]["worksheets"], 0)
        outbound = self.Transaction.search([("name", "=", "61000")])
        ordinary = self.Transaction.search([("name", "=", "61001")])
        self.assertEqual(len(outbound), 1)
        self.assertEqual(len(ordinary), 1)
        self.assertTrue(outbound.sale_order_id)
        self.assertTrue(ordinary.sale_order_id)
        self.assertEqual(self._on_hand(), on_hand)
        self.assertTrue(report.census["payables_reconciliation"]["closes"])
        erp_source_index.account_inventory_destinations(index, report)
        report.source_counts = index.counts()
        projected = summary.import_run_summary(report.as_dict())
        accounted = (
            projected["records_created"]
            + projected["records_updated"]
            + projected["records_unchanged"]
            + projected["records_rejected"]
        )
        self.assertEqual(projected["records_seen"], accounted)
        self.assertEqual(projected["final_status"], "partial")

        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self._on_hand(), on_hand)
        self.assertEqual(replay.counts["transactions"]["created"], 0)
        self.assertEqual(replay.counts["transaction_lines"]["created"], 0)
        self.assertEqual(len(self._marked("stock.location", "legacy_erp_inv_addr_")), 2)
        self.assertEqual(len(self._marked("purchase.order.line", "legacy_erp_pol_13303")), 1)
        self.assertEqual(len(self._marked("sale.order", "legacy_erp_so_")), 2)
        self.assertFalse(self.Transaction.search([("name", "=", "60403")]))

    def test_inventory_marker_follows_a_corrected_site_and_a_sale_only_line_is_rejected(self):
        """A corrected ShipToID moves the worksheet marker. A sale-only line is not counted as stored."""
        index = erp_source_index.build_source_index(
            SourcePayload(
                kind=PayloadKind.GRID,
                root=Path("."),
                tables={
                    "Address": [
                        {"AddressID": "404812", "CpID": "(INV)", "Type": "GREENVIEW WASHINGTON WAREHOUSE"},
                        {"AddressID": "405026", "CpID": "(INV)", "Type": "JEI DALLAS WAREHOUSE"},
                    ],
                },
            )
        )
        number = "62001"
        self._add_order(index, "30000", "33600", "PO", VENDOR, "2026-04-01 00:00:00")
        self._add_order(index, "30001", "18001", "SO", CUSTOMER, "2026-04-01 00:00:00")
        self._add_line(index, "30010", "33600", _line("15001", number, "", "30010", "100", "0", "100", "40"))
        self._add_line(index, "30011", "18001", _line("15002", number, "30011", "", "100", "50", "0", "0"))
        index.buysells[number] = _buysell(
            number, "2026-04-01 00:00:00", cust="(INV)", vendor=VENDOR, ShipToID="GREENVIEW WASHINGTON WAREHOUSE"
        )
        report = self._run(index)
        greenview = self._order("stock.location", "legacy_erp_inv_addr_404812")
        self.assertEqual(self._order("stock.location", "legacy_erp_inv_wks_62001"), greenview)
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_18001"))
        self.assertEqual(report.counts["transaction_lines"]["created"], 1)
        self.assertEqual(report.counts["transaction_lines"]["rejected"], 1)
        self.assertEqual(report.counts["transactions"]["skipped"], 1)

        index.buysells[number]["ShipToID"] = "JEI DALLAS WAREHOUSE"
        corrected = self._run(index)
        dallas = self._order("stock.location", "legacy_erp_inv_addr_405026")
        self.assertEqual(self._order("stock.location", "legacy_erp_inv_wks_62001"), dallas)
        self.assertNotEqual(dallas, greenview)
        self.assertFalse(self._marked("sale.order", "legacy_erp_so_18001"))
        self.assertEqual(corrected.counts["transaction_lines"]["created"], 0)
        self.assertEqual(corrected.counts["transaction_lines"]["skipped"], 1)
        self.assertEqual(corrected.counts["transaction_lines"]["rejected"], 1)

        before = self._snapshot()
        replay = self._run(index)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(replay.counts["transaction_lines"]["created"], 0)
        self.assertEqual(self._order("stock.location", "legacy_erp_inv_wks_62001"), dallas)

    def _closed_import(self, status):
        index = self._index()
        self._worksheet_54839(index)
        index.buysells["54839"]["status"] = status
        self._run(index)
        tx = self.Transaction.search([("name", "=", "54839")])
        self.assertEqual(len(tx), 1)
        self.assertEqual(tx.state, "closed")
        self.assertTrue(tx.legacy_erp_history)
        self.assertEqual(tx.legacy_erp_status, status)
        moves = self._marked("account.move", "legacy_erp_")
        self.assertTrue(moves)
        self.assertEqual(set(moves.mapped("state")), {"draft"})
        return tx, moves

    def test_unrecognized_source_status_creates_a_closed_transaction(self):
        self._closed_import("VOID?")

    def test_commercial_source_cancellation_creates_a_closed_transaction_and_replay_keeps_reopen(self):
        tx, moves = self._closed_import("X")
        manager = self.env["res.users"].create(
            {
                "name": "Worksheet Reopen Manager",
                "login": "worksheet_reopen_manager",
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("plasticos_transaction.group_plasticos_manager").id,
                        ]
                    )
                ],
            }
        )
        tx.with_user(manager).action_reopen_historical("source X is provenance only")
        index = self._index()
        self._worksheet_54839(index)
        index.buysells["54839"]["status"] = "X"
        self._run(index)
        tx.invalidate_recordset()
        moves.invalidate_recordset()
        self.assertEqual(tx.state, "active")
        self.assertEqual(tx.legacy_erp_status, "X")
        self.assertEqual(self.Transaction.search_count([("name", "=", "54839")]), 1)
        self.assertEqual(set(moves.mapped("state")), {"draft"})

    def test_confirmed_replay_fills_empty_material_fields_and_keeps_a_different_grade(self):
        index = self._index()
        number = "60707"
        self._add_order(index, "9604", "16003", "SO", CUSTOMER, "2026-07-03 00:00:00")
        self._add_order(index, "9605", "8003", "PO", VENDOR, "2026-07-03 00:00:00")
        for detail_id, grade in (("13620", "GRADE-FILM"), ("13621", "GRADE-FILM")):
            detail = _line(detail_id, number, "9804", "9805", "1000", "100", "1000", "80", grade)
            detail["InvoiceDesc"] = "clear film"
            index.lines[detail_id] = detail
            index.lines_by_buysell.setdefault(number, []).append(detail_id)
        index.order_lines["9804"] = {"PONumber": "16003"}
        index.order_lines["9805"] = {"PONumber": "8003"}
        index.buysells[number] = _buysell(number, "2026-07-03 00:00:00")
        index.payables_by_buysell[number] = [_payable("700107", number, VENDOR, "320", "50100", "8003")]
        self._run(index)
        sale = self._order("sale.order", "legacy_erp_so_16003")
        purchase_order = self._order("purchase.order", "legacy_erp_po_8003")
        sale_line = self._order("sale.order.line", "legacy_erp_sol_13620")
        purchase_line = self._order("purchase.order.line", "legacy_erp_pol_13621")
        self.assertEqual(sale.state, "sale")
        self.assertEqual(purchase_order.state, "draft")
        self.assertEqual(sale_line.form_id.code, "FILM")
        self.assertEqual(sale_line.packaging_type_id.code, "bales")
        drums = self.env["plasticos.material.grade"].search([("code", "=", "DRUMS")], limit=1)
        polymer = sale_line.product_id.product_tmpl_id.polymer_id
        for line in (sale_line, purchase_line):
            line.write({"form_id": False, "packaging_type_id": False, "material_grade_id": drums.id})
        report = self._run(index)
        sale_line = self._order("sale.order.line", "legacy_erp_sol_13620")
        purchase_line = self._order("purchase.order.line", "legacy_erp_pol_13621")
        for line in (sale_line, purchase_line):
            self.assertEqual(line.form_id.code, "FILM")
            self.assertEqual(line.packaging_type_id.code, "bales")
            self.assertEqual(line.material_grade_id.code, "DRUMS")
        self.assertEqual(sale_line.product_id.product_tmpl_id.polymer_id, polymer)
        kept = [
            row for row in report.anomalies if row["key"] in {"13620", "13621"} and "material_grade_id" in row["detail"]
        ]
        self.assertEqual(len(kept), 2)
        again = self._run(index)
        sale_line = self._order("sale.order.line", "legacy_erp_sol_13620")
        purchase_line = self._order("purchase.order.line", "legacy_erp_pol_13621")
        self.assertEqual(sale_line.form_id.code, "FILM")
        self.assertEqual(purchase_line.packaging_type_id.code, "bales")
        self.assertEqual(sale_line.material_grade_id.code, "DRUMS")
        self.assertTrue(again.anomalies)

    def _on_hand(self):
        quant = self.env["stock.quant"].search([])
        moves = self.env["stock.move"].search_count([]) if "stock.move" in self.env else 0
        return (sum(quant.mapped("quantity")), moves)

    def _order(self, model_name, xml_id):
        data = self.Data.search(
            [("module", "=", XMLID_MODULE), ("model", "=", model_name), ("name", "=", xml_id)],
            limit=1,
        )
        self.assertTrue(data, xml_id)
        return self.env[model_name].browse(data.res_id)
