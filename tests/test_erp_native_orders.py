"""Worksheet line keys resolve through the order line, then the header number."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plasticos_partner_import"))

from erp.native_orders import (  # noqa: E402
    freight_vendor_id,
    header_for_line,
    incoterm_code,
    newest_numbers,
    sale_note,
    unit_price,
    worksheet_commission,
    worksheet_log,
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


def test_newest_numbers_keeps_the_highest_worksheet_numbers():
    assert newest_numbers(["10001", "999", "54839"], 2) == ["10001", "54839"]
    assert newest_numbers(["3", "1"], None) == ["3", "1"]


def test_worksheet_commission_uses_the_filled_slot_and_reassigns_former_reps():
    code, amount = worksheet_commission(
        {"ReferrerNo1": None, "ReferrerNo2": "TF", "Commission1": "0", "Commission2": "168.28"}
    )
    assert code == "TF"
    assert amount == pytest.approx(168.28)
    code, amount = worksheet_commission(
        {"ReferrerNo1": "JB", "ReferrerNo2": "TF", "Commission1": "10", "Commission2": "5"}
    )
    assert code == "MM"
    assert amount == pytest.approx(15)
