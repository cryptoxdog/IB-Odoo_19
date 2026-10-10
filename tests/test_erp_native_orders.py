"""Worksheet line keys resolve through the order line, then the header number."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plasticos_partner_import"))

from erp.native_orders import (  # noqa: E402
    BASE_TRADE,
    CARRIED_BY_PAYABLES,
    CUSTOMER_CREDIT,
    CUSTOMER_DEBIT,
    NOT_REALIZED,
    PREPAY_OMITTED,
    SETTLEMENT_EVIDENCE,
    SHORT_TON_LB,
    TRANSACTION_ONLY_COST,
    UNAPPROVED,
    UNBILLABLE,
    amount_drift,
    commission_recipients,
    freight_vendor_id,
    header_for_line,
    incoterm_code,
    ledger_adjustment_kind,
    link_census,
    link_reason_class,
    native_quantity,
    newest_numbers,
    payable_matches_purchase,
    payables_reconciliation,
    purchase_bill_lines,
    quarantined_payable,
    sale_note,
    selected_worksheets,
    unit_price,
    with_worksheet,
    worksheet_commission,
    worksheet_log,
    worksheet_numbers,
    worksheet_outcome,
)


def _index():
    return SimpleNamespace(
        order_lines={"9227": {"PONumber": "14263"}, "9226": {"PONumber": "7275"}},
        orders={
            "6345": {
                "POID": "6345",
                "PONumber": "14263",
                "Source": "SO",
                "CpID": "1577",
                "PriceBasis": "Delivered",
            },
            "6344": {
                "POID": "6344",
                "PONumber": "7275",
                "Source": "PO",
                "CpID": "2213",
                "PriceBasis": "FOB Supplier Dock",
            },
            "9227": {"POID": "9227", "PONumber": "8693", "Source": "PO"},
        },
        orders_by_source_number={("SO", "14263"): ["6345"], ("PO", "7275"): ["6344"], ("PO", "8693"): ["9227"]},
    )


def test_sale_line_key_does_not_use_the_colliding_header_id():
    header, reason = header_for_line(_index(), "9227", "SO")
    assert reason == ""
    assert header["PONumber"] == "14263"
    assert header["POID"] == "6345"


def test_purchase_line_key_resolves_the_purchase_header():
    header, reason = header_for_line(_index(), "9226", "PO")
    assert reason == ""
    assert header["PONumber"] == "7275"


def test_incoterm_crosswalk_skips_the_do_not_use_basis():
    assert incoterm_code("FOB Supplier Dock") == "FOB"
    assert incoterm_code("Delivered") == "FAS"
    assert incoterm_code("Z - DO NOT USE") is None


def test_sale_note_joins_the_sticky_and_the_speech_bubble():
    assert sale_note("sticky", "bubble") == "<p>sticky<br/><br/>bubble</p>"
    assert sale_note("", "") == ""
    assert worksheet_log("sticky", "bubble") == "sticky\n\nbubble"
    assert worksheet_log("sticky", "", "RQSTD PU APT") == "sticky\n\nRQSTD PU APT"
    assert worksheet_log("", "") == ""
    assert worksheet_outcome("W") == "active"
    assert worksheet_outcome("I") == "closed"
    assert worksheet_outcome("X") == "cancelled"


def test_freight_vendor_is_the_nonzero_inland_freight_row():
    rows = [
        {"InvoiceDesc": "CHS Profit Split", "VendorID": "1292", "Cost": "0.00", "GLAcct": "50100"},
        {"InvoiceDesc": "", "VendorID": "2427", "Cost": "450.00", "GLAcct": "50200"},
    ]
    assert freight_vendor_id(rows) == "2427"
    assert freight_vendor_id([{"VendorID": "1292", "Cost": "0", "GLAcct": "50200"}]) == ""


def test_unit_price_uses_amount_over_worksheet_weight():
    assert unit_price("9763.95", "19145", "0") == pytest.approx(9763.95 / 19145)


def test_purchase_bill_uses_worksheet_weight_when_the_payable_is_the_purchase_total():
    rows = [
        {
            "PWeight": "36000",
            "PWeightUOM": "L",
            "PPrice": "0.12",
            "PAmount": "4320",
            "GradeID": "10059",
            "InvoiceDesc": "LDPE Film",
            "DetailID": "13620",
        }
    ]
    assert payable_matches_purchase(4320, rows)
    assert not payable_matches_purchase(255, rows)
    line = purchase_bill_lines(rows)[0]
    assert line["quantity"] == 36000
    assert line["price_unit"] == pytest.approx(0.12)
    assert line["uom"] == "L"
    assert line["detail_id"] == "13620"
    counted = purchase_bill_lines(
        [
            {
                "PWeight": "240",
                "PWeightUOM": "E",
                "PPrice": "3",
                "PAmount": "720",
                "GradeID": "881",
                "InvoiceDesc": "Gaylord Boxes",
            }
        ]
    )[0]
    assert counted["quantity"] == 240
    assert counted["uom"] == "E"


def test_newest_numbers_keeps_the_highest_worksheet_numbers():
    assert newest_numbers(["10001", "999", "54839"], 2) == ["10001", "54839"]
    assert newest_numbers(["3", "1"], None) == ["3", "1"]


def test_selected_worksheets_keeps_the_pinned_carrier_chargeback():
    selected = selected_worksheets(["58699", "60400", "60739"], 1)
    assert selected == ["60739", "58699"]
    assert selected_worksheets(["60400"], 1) == ["60400"]


def test_worksheet_commission_uses_the_slot_that_carries_the_amount():
    code, amount, slots = worksheet_commission(
        {"ReferrerNo1": None, "ReferrerNo2": "TF", "Commission1": "0", "Commission2": "168.28"}
    )
    assert code == "TF"
    assert amount == pytest.approx(168.28)
    assert slots == [{"slot": "2", "code": "TF", "amount": pytest.approx(168.28)}]
    # A named slot with no amount yields to the slot that was paid (2026 pattern: IB 0 / LR amount).
    code, amount, slots = worksheet_commission(
        {"ReferrerNo1": "IB", "ReferrerNo2": "LR", "Commission1": "0", "Commission2": "75.5"}
    )
    assert code == "LR"
    assert amount == pytest.approx(75.5)
    assert commission_recipients(slots) == ["LR"]


def test_worksheet_commission_keeps_the_historical_recipient_and_both_paid_slots():
    # A former representative is the historical recipient; the account reassignment is not applied.
    code, amount, slots = worksheet_commission(
        {"ReferrerNo1": "JB", "ReferrerNo2": None, "Commission1": "10", "Commission2": None}
    )
    assert code == "JB"
    assert amount == pytest.approx(10)
    # Two recipients each with an amount (worksheet 54119: GS 389.19 / TF 50).
    code, amount, slots = worksheet_commission(
        {"ReferrerNo1": "GS", "ReferrerNo2": "TF", "Commission1": "389.19", "Commission2": "50"}
    )
    assert code == "GS"
    assert amount == pytest.approx(439.19)
    assert commission_recipients(slots) == ["GS", "TF"]
    # No slot at all.
    code, amount, slots = worksheet_commission({"ReferrerNo1": None, "ReferrerNo2": "", "Commission1": None})
    assert (code, amount, slots) == ("", 0.0, [])
    # Named slot, nothing paid: the name is still the recipient, the amount is zero.
    code, amount, slots = worksheet_commission({"ReferrerNo1": "IB", "Commission1": "0"})
    assert (code, amount) == ("IB", 0.0)
    assert commission_recipients(slots) == []


def test_ledger_rows_route_by_source_adjustment_type_and_approval():
    assert ledger_adjustment_kind({"Source": "B"}) == BASE_TRADE
    credit = {"Source": "A", "AdjType": "S", "AdjApproved": "Y", "Sale": "-382.90", "LedgerID": "5694"}
    assert ledger_adjustment_kind(credit) == CUSTOMER_CREDIT
    debit = {"Source": "A", "AdjType": "S", "AdjApproved": "Y", "Sale": "14.06"}
    assert ledger_adjustment_kind(debit) == CUSTOMER_DEBIT
    assert ledger_adjustment_kind({"Source": "A", "AdjType": "P", "AdjApproved": "Y", "Cost": "-9366.52"}) == (
        CARRIED_BY_PAYABLES
    )
    assert ledger_adjustment_kind({"Source": "A", "AdjType": "S", "AdjApproved": "N", "Sale": "-5"}) == UNAPPROVED
    assert ledger_adjustment_kind({"Source": "A", "AdjType": "S", "Sale": "-5"}) == UNAPPROVED
    assert ledger_adjustment_kind({"Source": "D", "AdjType": "S", "AdjApproved": "Y"}) == SETTLEMENT_EVIDENCE
    assert ledger_adjustment_kind({"Source": "F", "AdjType": "S", "AdjApproved": "Y"}) == SETTLEMENT_EVIDENCE


def test_worksheet_origin_lists_every_worksheet_once():
    assert worksheet_numbers("") == []
    assert worksheet_numbers("54839") == ["54839"]
    assert with_worksheet("", "54840") == "54840"
    assert with_worksheet("54840", "54839") == "54839, 54840"
    assert with_worksheet("54839, 54840", "54840") == "54839, 54840"
    assert worksheet_numbers("54839, 54840") == ["54839", "54840"]


# ---------------------------------------------------------------------------
# Order-link exception census
# ---------------------------------------------------------------------------
def test_header_reason_names_a_number_that_exists_under_the_other_source():
    index = _index()
    index.order_lines["9300"] = {"PONumber": "7275"}  # a sale key whose number is a purchase order
    header, reason = header_for_line(index, "9300", "SO")
    assert header is None
    assert reason == "SO 7275 matched 0 headers (exists as PO)"
    assert link_reason_class(reason) == "number_under_other_source"
    index.order_lines["9301"] = {"PONumber": "99999"}
    assert header_for_line(index, "9301", "SO") == (None, "SO 99999 matched 0 headers")


def test_link_reason_classes_cover_every_header_for_line_reason():
    assert link_reason_class("blank line key") == "blank_key"
    assert link_reason_class("no order line for 123") == "key_without_order_line"
    assert link_reason_class("order line 123 has no PONumber") == "order_line_without_number"
    assert link_reason_class("SO 14263 matched 0 headers") == "number_without_header"
    assert link_reason_class("PO 7275 matched 0 headers (exists as SO)") == "number_under_other_source"
    assert link_reason_class("SO 14263 matched 2 headers") == "number_with_several_headers"


def _census_index():
    lines = {
        # 57001: no sale link on either line, purchase links, $900 of sale amount in the source
        "1": {"BuySellNo": "57001", "SAmount": "500", "PAmount": "400"},
        "2": {"BuySellNo": "57001", "SAmount": "400", "PAmount": "300"},
        # 57002: sale link on one line, the other line dangles on the purchase side
        "3": {"BuySellNo": "57002", "SAmount": "1000", "PAmount": "800"},
        "4": {"BuySellNo": "57002", "SAmount": "0", "PAmount": "50"},
        # 57003: fully linked
        "5": {"BuySellNo": "57003", "SAmount": "10", "PAmount": "5"},
    }
    return SimpleNamespace(
        lines=lines,
        lines_by_buysell={"57001": ["1", "2"], "57002": ["3", "4"], "57003": ["5"]},
        buysells={
            "57001": {"CustID": "1577", "VendorID": "2213", "OrderDt": "2019-03-01 00:00:00", "status": "I"},
            "57002": {"CustID": "9999", "VendorID": "2213", "OrderDt": "2024-05-01 00:00:00", "status": "W"},
            "57003": {"CustID": "1577", "VendorID": "2213", "OrderDt": "2024-05-01 00:00:00", "status": "I"},
        },
        counterparties={"1577": {}, "2213": {}},
        ledger_by_buysell={"57001": [{"Source": "B", "Sale": "900"}], "57002": [{"Source": "B", "Sale": "0"}]},
        receipts_by_buysell={"57001": [{"BuySellNo": "57001"}]},
        payables_by_buysell={"57001": [{"PayableID": "1"}], "57003": [{"PayableID": "2"}]},
    )


def test_link_census_counts_lines_worksheets_keys_and_dollars_by_root_cause():
    failures = [
        {"number": "57001", "detail_id": "1", "side": "sale", "key": "", "reason": "blank line key"},
        {"number": "57001", "detail_id": "2", "side": "sale", "key": "800", "reason": "no order line for 800"},
        {"number": "57002", "detail_id": "4", "side": "purchase", "key": "801", "reason": "no order line for 801"},
    ]
    links = {
        "57001": {"sale": False, "purchase": True},
        "57002": {"sale": True, "purchase": True},
        "57003": {"sale": True, "purchase": True},
    }
    census = link_census(_census_index(), failures, links)

    by_reason = {(group["side"], group["reason"]): group for group in census["lines_by_reason"]}
    assert by_reason[("sale", "blank_key")] == {
        "side": "sale",
        "reason": "blank_key",
        "lines": 1,
        "worksheets": 1,
        "distinct_keys": 0,
        "sale_amount": 500.0,
        "purchase_amount": 400.0,
    }
    assert by_reason[("sale", "key_without_order_line")]["lines"] == 1
    assert by_reason[("sale", "key_without_order_line")]["distinct_keys"] == 1
    assert by_reason[("purchase", "key_without_order_line")]["purchase_amount"] == 50.0

    unsold = census["worksheets"]["without_sale_link"]
    assert unsold["worksheets"] == 1
    assert unsold["numbers"] == ["57001"]
    assert unsold["lines"] == 2
    assert unsold["with_purchase_link"] == 1
    assert unsold["with_customer_trade_ledger"] == 1
    assert unsold["with_customer_receipts"] == 1
    assert unsold["with_payables"] == 1
    assert unsold["partner_active"] == 1
    assert unsold["partner_inactive_or_absent"] == 0
    assert unsold["sale_amount"] == 900.0
    assert unsold["purchase_amount"] == 700.0
    assert unsold["years"] == {"2019": 1}
    assert unsold["status"] == {"I": 1}
    assert census["worksheets"]["without_purchase_link"]["worksheets"] == 0


def test_link_census_reports_an_absent_customer_as_inactive_or_absent():
    links = {"57002": {"sale": False, "purchase": True}}
    census = link_census(_census_index(), [], links)
    view = census["worksheets"]["without_sale_link"]
    assert view["partner_inactive_or_absent"] == 1
    assert view["with_customer_trade_ledger"] == 0, "a zero-sale base trade row is not customer-invoice evidence"
    assert view["years"] == {"2024": 1}


# ---------------------------------------------------------------------------
# Weight and price fidelity
# ---------------------------------------------------------------------------
def test_short_tons_are_two_thousand_pounds_not_a_metric_tonne():
    assert SHORT_TON_LB == 2000.0
    assert native_quantity("20", "S") == (40000.0, "L")
    assert native_quantity("19145", "L") == (19145.0, "L")
    assert native_quantity("240", "e") == (240.0, "E")
    assert native_quantity("", "S") == (0.0, "L")
    # A short-ton purchase line bills 2,000 lb per ton at the per-pound rate; the amount is unchanged.
    line = purchase_bill_lines([{"PWeight": "20", "PWeightUOM": "S", "PPrice": "92", "PAmount": "1840"}])[0]
    assert line["quantity"] == 40000.0
    assert line["uom"] == "L"
    assert line["quantity"] * line["price_unit"] == pytest.approx(1840.0)


def test_amount_drift_is_the_cents_the_stored_line_cannot_reproduce():
    # 9,763.95 / 19,145 lb = 0.51 exactly: no drift at any precision.
    assert amount_drift("9763.95", 19145.0, 9763.95 / 19145, 2) == 0.0
    # 10,000 lb at 0.2441/lb = 2,441.00: a price field rounded to two decimals stores 0.24 and the
    # line reads 2,400.00; an unrounded price field (Odoo 19 ``price_unit``) reproduces the amount.
    assert amount_drift("2441", 10000.0, 0.2441, 2) == pytest.approx(-41.0)
    assert amount_drift("2441", 10000.0, 0.2441, 4) == 0.0
    assert amount_drift("2441", 10000.0, 0.2441, None) == 0.0
    # The quantity field's own precision counts too (``Product Unit``, two decimals).
    assert amount_drift("100", 3.333, 100 / 3.333, None, quantity_digits=2) == pytest.approx(-0.09)
    assert amount_drift("100", 3.333, 100 / 3.333, None, quantity_digits=None) == 0.0
    # A zero quantity cannot drift (the source price is carried as is).
    assert amount_drift("79.29", 0.0, 79.29, 2) == 0.0
    # Rounding within half a cent is not drift.
    assert amount_drift("1.00", 3.0, 1 / 3, 2) == pytest.approx(-0.01)
    assert amount_drift("0.99", 3.0, 0.33, 2) == 0.0
    assert amount_drift("1.00", 3.0, 1 / 3, None) == 0.0


# ---------------------------------------------------------------------------
# Unresolved source bills: quarantine and reconciliation
# ---------------------------------------------------------------------------
def test_quarantined_payable_keeps_the_full_source_identity():
    row = {
        "PayableID": " 502470 ",
        "BuySellNo": "51746",
        "CpID": "1380 ",
        "InvoiceNo": "4754 / 51746",
        "InvoiceDt": "2019-03-07 00:00:00",
        "Amount": "275",
        "GLAcct": "50300",
        "APBatchNo": "103189",
    }
    entry = quarantined_payable(row, "51746", "GL 50300 has no native account", TRANSACTION_ONLY_COST)
    assert entry == {
        "payable_id": "502470",
        "worksheet": "51746",
        "vendor": "1380",
        "invoice_no": "4754 / 51746",
        "invoice_date": "2019-03-07",
        "amount": 275.0,
        "gl": "50300",
        "batch": "103189",
        "reason": "GL 50300 has no native account",
        "disposition": TRANSACTION_ONLY_COST,
    }
    blank = quarantined_payable({"Amount": None, "GLAcct": None}, "1", "no GL", NOT_REALIZED)
    assert blank["payable_id"] == "" and blank["gl"] == "" and blank["amount"] == 0.0
    assert {TRANSACTION_ONLY_COST, NOT_REALIZED, PREPAY_OMITTED, UNBILLABLE} == {
        "transaction_only_cost",
        "not_realized",
        "prepay_omitted",
        "unbillable",
    }


def test_payables_reconciliation_closes_only_when_every_row_is_billed_or_quarantined():
    rows = [
        ("54839", "gl_50100_billed", 9366.52),
        ("54839", "gl_50100_billed", -9366.52),
        ("54839", "gl_50200_billed", 625.0),
        ("54839", "gl_50300_as_other_expenses", 100.0),
        ("54839", "gl_blank_not_realized", 40.0),
        ("54839", "prepay_batch_omitted", 5000.0),
        ("58001", "gl_50100_billed", 400.0),  # rolled back later: excluded from both sides
    ]
    quarantine = [
        {"worksheet": "54839", "payable_id": "600003", "amount": 100.0, "disposition": TRANSACTION_ONLY_COST},
        {"worksheet": "54839", "payable_id": "600009", "amount": 40.0, "disposition": NOT_REALIZED},
        {"worksheet": "54839", "payable_id": "600004", "amount": 5000.0, "disposition": PREPAY_OMITTED},
    ]
    result = payables_reconciliation(rows, quarantine, {"58001"})
    assert result["rows_seen"] == 6
    assert result["billed_rows"] == 3
    assert result["billed_amount"] == pytest.approx(625.0)
    assert result["quarantined_rows"] == 3
    assert result["quarantined_amount"] == pytest.approx(5140.0)
    assert result["by_disposition"] == {
        NOT_REALIZED: {"rows": 1, "amount": 40.0},
        PREPAY_OMITTED: {"rows": 1, "amount": 5000.0},
        TRANSACTION_ONLY_COST: {"rows": 1, "amount": 100.0},
    }
    assert result["closes"] is True
    # A row that was neither billed nor quarantined cannot read as imported.
    short = payables_reconciliation(rows, quarantine[:2], {"58001"})
    assert short["closes"] is False
    assert payables_reconciliation([], [], set()) == {
        "rows_seen": 0,
        "billed_rows": 0,
        "billed_amount": 0.0,
        "quarantined_rows": 0,
        "quarantined_amount": 0.0,
        "by_disposition": {},
        "closes": True,
    }
