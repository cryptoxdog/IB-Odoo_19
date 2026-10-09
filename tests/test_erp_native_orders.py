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
    SETTLEMENT_EVIDENCE,
    UNAPPROVED,
    commission_recipients,
    freight_vendor_id,
    header_for_line,
    incoterm_code,
    ledger_adjustment_kind,
    newest_numbers,
    payable_matches_purchase,
    purchase_bill_lines,
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
