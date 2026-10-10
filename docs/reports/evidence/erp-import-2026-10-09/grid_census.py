#!/usr/bin/env python3
"""Source-side census on the frozen 2026-08-07 grid (regression fixture, not runtime authority).

The grid carries no ``PO`` / ``PODetail`` / ``BuySell`` extract and no ``SPO_ID`` /
``PPO_ID`` columns, so the order-link figures here are a *header-reference proxy*
(``WKSDetail.SPo`` / ``PPo`` blank), not the foreign-key census the direct-SQL run
emits in ``<report>-census.json``. The price-precision and payables figures are
exact for the grid's rows.

Usage (repo root):  python3 docs/reports/evidence/erp-import-2026-10-09/grid_census.py
"""

from __future__ import annotations

import collections
import csv
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "plasticos_partner_import"))
from erp.native_orders import EXPENSE_GL, FREIGHT_GL, MATERIAL_GL, native_quantity  # noqa: E402

BULK = ROOT / "plasticos_partner_import" / "erp_extracted_data" / "bulk"
CENT = Decimal("0.01")


def _rows(name: str) -> list[dict]:
    with (BULK / f"{name}.csv").open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _num(value: str | None) -> Decimal:
    text = (value or "").strip()
    return Decimal(text) if text and text != "NULL" else Decimal(0)


def _text(value: str | None) -> str:
    text = (value or "").strip()
    return "" if text == "NULL" else text


def _money(value: Decimal) -> str:
    return f"{value.quantize(CENT, rounding=ROUND_HALF_UP):,}"


def link_proxy(lines: list[dict], ledger: list[dict], receipts: list[dict], payables: list[dict]) -> None:
    print("== order-link proxy (WKSDetail.SPo / PPo header references; grid has no SPO_ID/PPO_ID) ==")
    by_ws: dict[str, list[dict]] = collections.defaultdict(list)
    for row in lines:
        by_ws[_text(row["BuySellNo"])].append(row)
    trade_sale = {_text(r["BuySellNo"]) for r in ledger if _text(r["Source"]).upper() == "B" and _num(r["Sale"])}
    years = {}
    for row in ledger:
        number = _text(row["BuySellNo"])
        year = _text(row["TradeDt"])[:4]
        if number and year:
            years.setdefault(number, year)
    with_receipt = {_text(r["BuySellNo"]) for r in receipts}
    with_payable = {_text(r["BuySellNo"]) for r in payables}
    for side, column, other in (("sale", "SPo", "PPo"), ("purchase", "PPo", "SPo")):
        blank = [row for row in lines if not _text(row[column])]
        numbers = sorted({_text(row["BuySellNo"]) for row in blank})
        unlinked = [n for n in numbers if all(not _text(row[column]) for row in by_ws[n])]
        print(f"{side}: lines with blank {column} {len(blank)} on {len(numbers)} worksheets")
        print(
            f"  of those lines: SAmount {_money(sum((_num(r['SAmount']) for r in blank), Decimal(0)))}"
            f"  PAmount {_money(sum((_num(r['PAmount']) for r in blank), Decimal(0)))}"
            f"  with {other} present {sum(1 for r in blank if _text(r[other]))}"
        )
        print(f"  worksheets with no {column} on any line: {len(unlinked)}")
        rows = [row for n in unlinked for row in by_ws[n]]
        print(
            f"    lines {len(rows)}  SAmount {_money(sum((_num(r['SAmount']) for r in rows), Decimal(0)))}"
            f"  PAmount {_money(sum((_num(r['PAmount']) for r in rows), Decimal(0)))}"
            f"  with {other} link {sum(1 for n in unlinked if any(_text(r[other]) for r in by_ws[n]))}"
            f"  with base-trade sale ledger {sum(1 for n in unlinked if n in trade_sale)}"
            f"  with receipts {sum(1 for n in unlinked if n in with_receipt)}"
            f"  with payables {sum(1 for n in unlinked if n in with_payable)}"
        )
        by_year = collections.Counter(years.get(n, "unknown") for n in unlinked)
        print(f"    trade years: {dict(sorted(by_year.items()))}")


def price_precision(lines: list[dict]) -> None:
    print("== price precision: source amount vs quantity x unit price as Odoo would store it ==")
    print(
        "Odoo 19 sale/purchase/invoice price_unit is a Float with min_display_digits='Product Price' and no"
        " digits, so the stored value is unrounded (float8); quantities store at 'Product Unit' (2 decimals)."
    )
    for digits in (None, 2, 3, 4, 5, 6):
        quantum = Decimal(1).scaleb(-digits) if digits is not None else None
        count = 0
        net = Decimal(0)
        absolute = Decimal(0)
        biggest = Decimal(0)
        for side in ("S", "P"):
            for row in lines:
                amount = _num(row[f"{side}Amount"])
                quantity, _uom = native_quantity(row[f"{side}Weight"], row[f"{side}WeightUOM"])
                if not amount or not quantity:
                    continue
                stored_quantity = Decimal(str(quantity)).quantize(CENT, rounding=ROUND_HALF_UP)
                unit = amount / Decimal(str(quantity))
                stored_unit = unit.quantize(quantum, rounding=ROUND_HALF_UP) if quantum is not None else unit
                stored = (stored_unit * stored_quantity).quantize(CENT, rounding=ROUND_HALF_UP)
                drift = stored - amount
                if drift:
                    count += 1
                    net += drift
                    absolute += abs(drift)
                    biggest = max(biggest, abs(drift))
        label = "stored (unrounded price)" if digits is None else f"if price were rounded to {digits} decimals"
        print(
            f"{label:<40}: lines with drift {count:>5}  net {_money(net):>12}  abs {_money(absolute):>12}"
            f"  max {_money(biggest):>8}"
        )
    weights = collections.Counter()
    for row in lines:
        for side in ("S", "P"):
            text = _text(row[f"{side}Weight"])
            weights[len(text.split(".")[1]) if "." in text else 0] += 1
    print(f"weight decimal places in the source (quantity stores at 2): {dict(sorted(weights.items()))}")
    short = [row for row in lines if "S" in (_text(row["SWeightUOM"]), _text(row["PWeightUOM"]))]
    print(f"short-ton lines (UoM S on either side): {len(short)}")
    for row in short:
        print(
            f"  DetailID {row['DetailID']} ws {_text(row['BuySellNo'])}: sale {_text(row['SWeight'])} {_text(row['SWeightUOM'])}"
            f" @ {_text(row['SPrice'])}/{_text(row['SPriceUOM'])} = {_text(row['SAmount'])};"
            f" buy {_text(row['PWeight'])} {_text(row['PWeightUOM'])} @ {_text(row['PPrice'])}/{_text(row['PUOM'])}"
            f" = {_text(row['PAmount'])}"
        )


def payables_census(payables: list[dict], counterparties: dict[str, dict], batches: list[dict]) -> None:
    print("== Payables routing by GL lookup ==")
    prepay = {_text(r["APBatchNo"]) for r in batches if _text(r["PrePay"]) == "1"}
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for row in payables:
        gl = _text(row["GLAcct"])
        if _text(row["APBatchNo"]) in prepay:
            bucket = "prepay_batch_omitted"
        elif gl == MATERIAL_GL:
            bucket = "gl_50100_material_bill"
        elif gl == FREIGHT_GL:
            bucket = "gl_50200_freight_bill"
        elif gl in EXPENSE_GL:
            bucket = f"gl_{gl}_as_other_expenses"
        else:
            bucket = f"gl_{gl or 'blank'}_not_realized"
        groups[bucket].append(row)
    for bucket, rows in sorted(groups.items()):
        vendors = {_text(r["CpID"]) for r in rows}
        inactive = [r for r in rows if _text(r["CpID"]) not in counterparties]
        print(
            f"{bucket:<30} rows {len(rows):>6}  worksheets {len({_text(r['BuySellNo']) for r in rows}):>5}"
            f"  amount {_money(sum((_num(r['Amount']) for r in rows), Decimal(0))):>14}  vendors {len(vendors):>4}"
            f"  with InvoiceNo {sum(1 for r in rows if _text(r['InvoiceNo'])):>6}"
            f"  vendor not in active counterparties {len(inactive):>4} ({_money(sum((_num(r['Amount']) for r in inactive), Decimal(0)))})"
        )
    for bucket in ("gl_50300_as_other_expenses", "gl_50600_as_other_expenses", "gl_blank_not_realized"):
        rows = groups.get(bucket, [])
        top = collections.Counter(_text(r["CpID"]) for r in rows).most_common(6)
        print(f"  {bucket} top vendors:")
        for cp_id, count in top:
            name = (counterparties.get(cp_id) or {}).get("CompanyNm", "(not in active counterparties)")
            amount = sum((_num(r["Amount"]) for r in rows if _text(r["CpID"]) == cp_id), Decimal(0))
            print(f"    {cp_id} {name[:32]:<32} rows {count:>4} amount {_money(amount):>12}")


def main() -> int:
    lines = _rows("WKSDetail")
    print(f"grid WKSDetail lines: {len(lines)} (the 2026-10-09 SQL run read 11 441)")
    link_proxy(lines, _rows("GPLedger"), _rows("Receipt"), _rows("Payables"))
    price_precision(lines)
    counterparties = {_text(r["CpID"]): r for r in _rows("CounterParty")}
    payables_census(_rows("Payables"), counterparties, _rows("PayablesBatch"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
