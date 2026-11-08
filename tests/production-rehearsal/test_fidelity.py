"""Independent ERP mapping fidelity. Fixtures stand in for persisted Odoo rows."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

KIT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("rehearsal_fidelity", KIT / "fidelity.py")
fid = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fid)


def _bundles():
    odoo, source = fid.fixture_bundles()
    return copy.deepcopy(odoo), copy.deepcopy(source)


def _failed(report, field):
    return [row for row in report["rows"] if row["result"] == "FAIL" and row["target_field"] == field]


def test_fixture_snapshot_matches_and_names_the_derived_quantity_rule():
    report = fid.evaluate(*_bundles())
    assert report["evidence"] == "complete"
    assert report["status"] == "PASS"
    assert report["failed"] == 0
    assert report["compared"] > 0
    quantity = next(row for row in report["rows"] if row["target_field"] == "product_uom_qty")
    assert quantity["expected"] == 2000
    assert quantity["actual"] == 2000
    assert quantity["result"] == "PASS"
    rule = next(row for row in fid.COVERAGE if row["source_field"] == "SWeight,SWeightUOM")
    assert "2000" in rule["formula"]
    source = (KIT / "fidelity.py").read_text(encoding="utf-8")
    assert "import plasticos_partner_import" not in source
    assert "from plasticos_partner_import" not in source


def test_short_ton_conversion_and_a_wrong_persisted_quantity_fail():
    assert fid.native_quantity("2.5", "S") == (5000.0, "L")
    assert fid.native_quantity("12", "L") == (12.0, "L")
    assert fid.native_quantity("3", "E") == (3.0, "E")
    assert fid.unit_price("1000", 2000.0, "999") == 0.5
    assert fid.unit_price("10", 0.0, "4") == 4.0
    odoo, source = _bundles()
    odoo["sale_lines"][0]["qty"] = 1
    report = fid.evaluate(odoo, source)
    assert report["status"] == "FAIL"
    assert _failed(report, "product_uom_qty")[0]["expected"] == 2000


def test_negative_sale_is_a_refund_for_the_absolute_amount():
    odoo, source = _bundles()
    source["details"]["900"]["SAmount"] = "-1000"
    source["details_by_token"]["900"] = source["details"]["900"]
    odoo["sale_lines"][0]["price"] = -0.5
    odoo["invoices"][0]["move_type"] = "out_refund"
    report = fid.evaluate(odoo, source)
    assert report["status"] == "PASS"
    move = next(row for row in report["rows"] if row["target_field"] == "move_type" and row["source_id"] == "100")
    assert move["expected"] == "out_refund"
    total = next(row for row in report["rows"] if row["target_field"] == "amount_total" and row["source_id"] == "100")
    assert total["expected"] == 1000


def test_blank_invoice_date_stays_blank_and_a_substituted_date_fails():
    odoo, source = _bundles()
    source["buysell"]["100"]["InvoiceDt"] = ""
    odoo["invoices"][0]["invoice_date"] = ""
    blank = fid.evaluate(odoo, source)
    assert blank["status"] == "PASS"
    undated = next(row for row in blank["rows"] if row["source_field"] == "InvoiceDt")
    assert undated["classification"] == "unmapped"
    assert undated["actual"] is None
    odoo["invoices"][0]["invoice_date"] = "2024-03-01"
    filled = fid.evaluate(odoo, source)
    assert filled["status"] == "FAIL"
    assert _failed(filled, "invoice_date")


def test_missing_source_counterparty_fails_and_is_not_a_pass():
    odoo, source = _bundles()
    del source["counterparties"]["10"]
    report = fid.evaluate(odoo, source)
    assert report["status"] == "FAIL"
    missing = _failed(report, "name")
    assert missing
    assert missing[0]["expected"] is None
    assert "no source row" in missing[0]["detail"]


def test_rejected_source_row_is_distinguished_from_a_mapping_defect():
    odoo, source = _bundles()
    unresolved = [
        {"table": "Address", "kind": "parent_not_imported", "key": "8", "detail": "counterparty was not created"}
    ]
    report = fid.evaluate(odoo, source, unresolved)
    assert report["status"] == "PASS"
    rejected = next(row for row in report["rows"] if row["classification"] == "rejected")
    assert rejected["result"] == "PASS"
    assert rejected["source_id"] == "8"
    assert rejected["actual"] is None
    odoo["sale_lines"][0]["qty"] = 1
    broken = fid.evaluate(odoo, source, unresolved)
    assert broken["status"] == "FAIL"
    assert any(row["classification"] == "rejected" for row in broken["rows"])
    assert _failed(broken, "product_uom_qty")


def test_cent_reproduction_is_precision_and_a_larger_gap_is_a_defect():
    odoo, source = _bundles()
    odoo["sale_lines"][0]["price"] = 0.500004
    precise = fid.evaluate(odoo, source)
    price = next(
        row
        for row in precise["rows"]
        if row["target_field"] == "price_unit" and row["target_model"] == "sale.order.line"
    )
    assert price["result"] == "PASS"
    assert price["classification"] == "precision"
    assert price["tolerance"] == fid.PRICE_TOLERANCE
    odoo["sale_lines"][0]["price"] = 0.75
    report = fid.evaluate(odoo, source)
    assert report["status"] == "FAIL"
    assert _failed(report, "price_unit")[0]["classification"] == "defect"


def test_purchase_approval_date_uses_the_earliest_trade_date_only():
    odoo, source = _bundles()
    source["ledger"]["100"] = ["2024-04-01 00:00:00", "2024-03-02 06:00:00"]
    report = fid.evaluate(odoo, source)
    approved = next(row for row in report["rows"] if row["target_field"] == "date_approve")
    assert approved["result"] == "PASS"
    assert approved["expected"].startswith("2024-03-02")
    source["ledger"]["100"] = []
    odoo["purchase_orders"][0]["date_approve"] = "2024-03-02 06:00:00"
    missing = fid.evaluate(odoo, source)
    assert _failed(missing, "date_approve")[0]["detail"].startswith("date_approve was set without")
    odoo["purchase_orders"][0]["date_approve"] = ""
    empty = fid.evaluate(odoo, source)
    row = next(item for item in empty["rows"] if item["target_field"] == "date_approve")
    assert row["result"] == "PASS"
    assert row["classification"] == "unmapped"


def test_posted_historical_invoice_and_inactive_contact_fail():
    odoo, source = _bundles()
    odoo["invoices"][0]["state"] = "posted"
    posted = fid.evaluate(odoo, source)
    assert _failed(posted, "state")[0]["actual"] == "posted"
    odoo, source = _bundles()
    source["contacts"]["5"]["IsActive"] = "N"
    inactive = fid.evaluate(odoo, source)
    assert inactive["status"] == "FAIL"
    assert any(row["source_field"] == "IsActive" and row["result"] == "FAIL" for row in inactive["rows"])


def test_internal_mailbox_is_not_the_company_email_and_an_unknown_role_stays_empty():
    assert fid.external_email("buyer@acme.example; staff@scrapmanagement.com") == "buyer@acme.example"
    odoo, source = _bundles()
    source["counterparties"]["10"]["Role"] = "Z"
    odoo["partners"][0]["company_role"] = ""
    odoo["partners"][0]["supplier_rank"] = 0
    report = fid.evaluate(odoo, source)
    role = next(row for row in report["rows"] if row["target_field"] == "company_role")
    assert role["result"] == "PASS"
    assert role["expected"] == ""


def test_incomplete_evidence_cannot_pass():
    odoo, source = _bundles()
    odoo["evidence"] = "missing"
    odoo["missing_reason"] = "clone snapshot was not read"
    report = fid.evaluate(odoo, source)
    assert report["status"] == "FAIL"
    assert report["evidence"] == "missing"
    assert report["rows"][0]["result"] == "FAIL"


def test_company_credit_limit_reads_the_company_value_and_email_is_stored_direct():
    odoo, source = _bundles()
    odoo["partners"][0]["credit_limit"] = {"1": 500.0}
    odoo["partners"][0]["email"] = "buyer@acme.example; staff@scrapmanagement.com"
    source["counterparties"]["10"]["APEMail"] = "buyer@acme.example; staff@scrapmanagement.com"
    report = fid.evaluate(odoo, source)
    credit = next(row for row in report["rows"] if row["target_field"] == "credit_limit")
    assert credit["result"] == "PASS"
    assert credit["actual"] == 500.0
    email = next(
        row for row in report["rows"] if row["target_field"] == "email" and row["source_table"] == "CounterParty"
    )
    assert email["result"] == "PASS"
    assert "scrapmanagement.com" in email["expected"]
    odoo["partners"][0]["credit_limit"] = {"1": 1.0}
    broken = fid.evaluate(odoo, source)
    assert _failed(broken, "credit_limit")[0]["actual"] == 1.0


def test_confirmed_sale_order_passes_and_a_done_order_fails():
    odoo, source = _bundles()
    odoo["sale_orders"][0]["state"] = "sale"
    confirmed = fid.evaluate(odoo, source)
    state = next(
        row for row in confirmed["rows"] if row["target_model"] == "sale.order" and row["target_field"] == "state"
    )
    assert state["result"] == "PASS"
    assert state["actual"] == "sale"
    odoo["sale_orders"][0]["state"] = "done"
    done = fid.evaluate(odoo, source)
    assert _failed(done, "state")[0]["actual"] == "done"


def test_blank_sale_key_is_omitted_from_the_invoice_total():
    odoo, source = _bundles()
    source["details"]["901"] = {
        "DetailID": "901",
        "BuySellNo": "100",
        "InvoiceDesc": "adjustment",
        "SWeight": "10",
        "SWeightUOM": "L",
        "SPrice": "-5",
        "SAmount": "-50",
        "SPO_ID": "",
        "PWeight": "",
        "PWeightUOM": "",
        "PPrice": "",
        "PAmount": "",
    }
    report = fid.evaluate(odoo, source)
    assert report["status"] == "PASS"
    total = next(row for row in report["rows"] if row["target_field"] == "amount_total" and row["source_id"] == "100")
    assert total["expected"] == 1000
    omitted = next(row for row in report["rows"] if row["source_id"] == "901")
    assert omitted["classification"] == "rejected"
    assert omitted["result"] == "PASS"


def test_material_bill_stores_absolute_purchase_lines():
    odoo, source = _bundles()
    source["details"]["901"] = {
        "DetailID": "901",
        "BuySellNo": "100",
        "SWeight": "0",
        "SWeightUOM": "L",
        "SAmount": "0",
        "SPO_ID": "",
        "PWeight": "10",
        "PWeightUOM": "L",
        "PPrice": "-10",
        "PAmount": "-100",
    }
    source["payables_by_token"]["55"]["Amount"] = "300"
    source["payables_by_token"]["55"]["GLAcct"] = "50100"
    odoo["bills"][0]["amount_total"] = 500
    report = fid.evaluate(odoo, source)
    total = next(row for row in report["rows"] if row["target_field"] == "amount_total" and row["source_id"] == "55")
    assert total["result"] == "PASS"
    assert total["expected"] == 500
    assert "absolute" in total["detail"]


def test_later_same_name_address_fills_a_blank_company_street2():
    odoo, source = _bundles()
    source["addresses"]["70"]["Addr1"] = "Acme"
    source["addresses"]["71"] = {
        "AddressID": "71",
        "CpID": "10",
        "Type": "DELIVERY ADDRESS",
        "Addr1": "Acme",
        "Addr2": "1 Main",
        "Addr3": "BLDG 34",
        "City": "Austin",
        "PostalCd": "78701",
    }
    odoo["partners"][0]["street2"] = "BLDG 34"
    report = fid.evaluate(odoo, source)
    street2 = next(row for row in report["rows"] if row["target_field"] == "street2")
    assert street2["result"] == "PASS"
    assert street2["expected"] == "BLDG 34"
    assert street2["source_id"] == "71"


def test_unseeded_unit_code_keeps_the_product_default_unit():
    odoo, source = _bundles()
    source["details"]["900"]["SWeight"] = "2000"
    source["details"]["900"]["SWeightUOM"] = "A"
    source["details"]["900"]["SPrice"] = "0.5"
    source["details_by_token"]["900"] = source["details"]["900"]
    odoo["sale_lines"][0]["uom_xml"] = "uom.product_uom_unit"
    kept = fid.evaluate(odoo, source)
    unit = next(row for row in kept["rows"] if row["target_field"] == "product_uom_id" and row["source_id"] == "900")
    assert unit["result"] == "PASS"
    assert unit["classification"] == "unmapped"
    odoo["sale_lines"][0]["uom_xml"] = "uom.product_uom_lb"
    written = fid.evaluate(odoo, source)
    assert _failed(written, "product_uom_id")[0]["actual"] == "uom.product_uom_lb"


def _order(name, kind, origin, incoterm):
    prefix = "legacy_erp_so_" if kind == "sale_orders" else "legacy_erp_po_"
    row = {
        "xmlid": f"{prefix}{name}",
        "name": name,
        "origin": origin,
        "date_order": "2020-02-05 00:00:00",
        "incoterm_code": incoterm,
        "state": "draft",
    }
    if kind == "sale_orders":
        row["client_order_ref"] = ""
    else:
        row["date_approve"] = ""
    return row


def _incoterm(report, name):
    return next(row for row in report["rows"] if row["target_field"] == "incoterm" and row["source_id"] == name)


# The five orders from the 2026-11-08 rehearsal. Each PO header basis is empty.
# Worksheet bases are the restored source. 5429 applies Delivered and then two
# later FOB worksheets, so FOB is the value the importer writes.
_FIVE = (
    ("11998", "sale_orders", "SO", "52225", {"52225": "FOB Supplier Dock"}),
    ("4998", "purchase_orders", "PO", "52046", {"52046": "FOB Supplier Dock"}),
    ("5281", "purchase_orders", "PO", "52416, 52417", {"52416": "FOB Supplier Dock", "52417": "FOB Supplier Dock"}),
    ("5289", "purchase_orders", "PO", "52426", {"52426": "FOB Supplier Dock"}),
    (
        "5429",
        "purchase_orders",
        "PO",
        "52597, 52598, 52599, 52600",
        {
            "52597": "FOB Supplier Dock",
            "52598": "Delivered",
            "52599": "FOB Supplier Dock",
            "52600": "FOB Supplier Dock",
        },
    ),
)


def test_empty_header_uses_the_last_worksheet_basis_for_the_five_rehearsal_orders():
    odoo, source = _bundles()
    for name, kind, side, origin, bases in _FIVE:
        odoo[kind].append(_order(name, kind, origin, "FOB"))
        source["orders"][f"{name}|{side}"] = {
            "PONumber": name,
            "Source": side,
            "PODate": "2020-02-05 00:00:00",
            "PriceBasis": "",
        }
        for number, basis in bases.items():
            source["buysell"][number] = {"BuySellNo": number, "PriceBasis": basis, "OrderDt": "", "InvoiceDt": ""}
    report = fid.evaluate(odoo, source)
    assert report["status"] == "PASS"
    for name, _kind, _side, _origin, _bases in _FIVE:
        row = _incoterm(report, name)
        assert row["result"] == "PASS"
        assert row["expected"] == "FOB"
        assert row["actual"] == "FOB"
        assert row["source_value"] == "FOB Supplier Dock"
        assert row["source_table"] == "BuySell"
    delivered_last = _incoterm(
        fid.evaluate(
            *_with_basis(
                odoo,
                source,
                "9001",
                "purchase_orders",
                "PO",
                "1, 2",
                {"1": "FOB Supplier Dock", "2": "Delivered"},
                "FOB",
            )
        ),
        "9001",
    )
    assert delivered_last["result"] == "FAIL"
    assert delivered_last["expected"] == ""
    assert delivered_last["source_value"] == "Delivered"


def _with_basis(odoo, source, name, kind, side, origin, bases, actual):
    left, right = copy.deepcopy(odoo), copy.deepcopy(source)
    left[kind].append(_order(name, kind, origin, actual))
    right["orders"][f"{name}|{side}"] = {
        "PONumber": name,
        "Source": side,
        "PODate": "2020-02-05 00:00:00",
        "PriceBasis": "",
    }
    for number, basis in bases.items():
        right["buysell"][number] = {"BuySellNo": number, "PriceBasis": basis, "OrderDt": "", "InvoiceDt": ""}
    return left, right


def test_header_basis_blocks_a_later_worksheet_and_string_order_is_the_importer_order():
    assert fid.effective_price_basis({"PriceBasis": "FOB"}, "10", {"10": {"PriceBasis": "Delivered"}}) == (
        "FOB",
        "PO",
        "",
    )
    # "10" sorts before "9", so worksheet 9 is the last write. Numeric order would let Delivered win.
    basis, table, winner = fid.effective_price_basis(
        {"PriceBasis": ""},
        "9, 10",
        {"10": {"PriceBasis": "Delivered"}, "9": {"PriceBasis": "FOB Supplier Dock"}},
    )
    assert (basis, table, winner) == ("FOB Supplier Dock", "BuySell", "9")


def test_failure_only_retention_matches_full_detection_and_coverage():
    odoo, source = _bundles()
    odoo["partners"][0]["name"] = "Wrong"
    for name, kind, side, origin, bases in _FIVE:
        odoo[kind].append(_order(name, kind, origin, "FOB"))
        source["orders"][f"{name}|{side}"] = {
            "PONumber": name,
            "Source": side,
            "PODate": "2020-02-05 00:00:00",
            "PriceBasis": "",
        }
        for number, basis in bases.items():
            source["buysell"][number] = {"BuySellNo": number, "PriceBasis": basis, "OrderDt": "", "InvoiceDt": ""}
    full = fid.evaluate(odoo, source)
    compact = fid.evaluate(odoo, source, retain_passes=False)
    assert full["failed"] >= 1
    assert compact["rows_retained"] == "failures"
    assert compact["compared"] == full["compared"]
    assert compact["failed"] == full["failed"]
    assert compact["rejected"] == full["rejected"]
    assert compact["unmapped"] == full["unmapped"]
    assert compact["precision"] == full["precision"]
    assert compact["coverage"] == full["coverage"]
    assert compact["source_fingerprint"] == full["source_fingerprint"]
    assert compact["rows"] == [row for row in full["rows"] if row["result"] == "FAIL"]
    assert all(
        row["result"] == "PASS"
        for row in full["rows"]
        if row["target_field"] == "incoterm" and row["source_id"] in {item[0] for item in _FIVE}
    )


def test_source_identifiers_stay_one_bound_parameter():
    import sys

    sys.path.insert(0, str(KIT))
    spec = importlib.util.spec_from_file_location("rehearsal_fidelity_run", KIT / "fidelity_run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params):
            self.calls.append((statement, params))

        def fetchall(self):
            return []

    cursor = Cursor()
    statement = "SELECT 1 WHERE id IN (SELECT CAST(%s AS nvarchar(max)))"
    module._rows(cursor, statement, ["10", "10", "20"])
    assert cursor.calls == [(statement, ("10\x1f20",))]
    assert ".format(" not in module._rows.__code__.co_consts
