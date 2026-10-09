"""ERP worksheet import against the real ORM.

These run under ``odoo --test-enable --test-tags /plasticos_transaction`` on a
database that carries the PlasticOS stack. The source rows are built in the
test from the shapes the SQL projections return; no source database is read.
"""

from __future__ import annotations

from datetime import date

from odoo import Command
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
        ]
        index.prepay_batches.add("PP-1")
        index.ledger_by_buysell["54839"] = [
            _ledger("5462", "54839", "B", None, None, sale="9763.95", cost="8826.48"),
            _ledger("5694", "54839", "A", "S", "Y", sale="-382.90", memo="CM 54839", title="CREDIT MEMO"),
            _ledger("5695", "54839", "A", "P", "Y", cost="-9366.52", cp_id=VENDOR),
            _ledger("5696", "54839", "A", "S", "N", sale="-1"),
            _ledger("5697", "54839", "D", "S", "Y", sale="-45.11"),
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
            "sale_origins": sorted(self.env["sale.order"].search([]).mapped("origin")),
            "purchase_origins": sorted(self.env["purchase.order"].search([]).mapped("origin")),
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
        self.assertAlmostEqual(tx.revenue_total, 9763.95 - 382.90, places=2)

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
        self.assertAlmostEqual(tx.gross_margin, (9763.95 - 382.90) - 8826.48 - 600.0 - 100.0, places=2)

        self.assertFalse(self._marked("account.move", "legacy_erp_ininv_600004"), "prepay batch row is not a bill")
        self.assertFalse(
            self._marked("account.move", "legacy_erp_ledger_5695"), "vendor adjustment is carried by Payables"
        )
        self.assertFalse(
            self._marked("account.move", "legacy_erp_ledger_5696"), "unapproved adjustment is not a document"
        )
        self.assertFalse(self._marked("account.move", "legacy_erp_ledger_5697"), "discount row is settlement evidence")
        details = {(item["table"], item["key"], item["detail"]) for item in report.anomalies}
        self.assertIn(("Payables", "600004", "prepay batch omitted"), details)
        self.assertIn(("GPLedger", "5696", "unapproved adjustment omitted"), details)
        self.assertIn(("GPLedger", "5697", "Source D row is settlement evidence"), details)

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
        self.assertEqual(tx["60002"].commission_payout_state, "paid")
        self.assertEqual(tx["60004"].commission_payout_state, "paid", "2026-05-31 is settled history")
        self.assertEqual(tx["60005"].commission_payout_state, "unpaid", "2026-06-01 is on or after the cutoff")
        self.assertEqual(tx["60002"].sale_order_id.date_order.date(), date(2022, 1, 5))
        # The payout model belongs to plasticos_commission, which depends on this module and
        # not the reverse, so it is not referenced here. A locked "paid" state is what keeps the
        # commission engine from generating a payout for settled history.
        self.assertTrue(all(t.commission_payout_state in ("paid", "unpaid") for t in tx.values()))
