"""Resolve worksheet lines onto native sale and purchase headers.

Odoo-free. ``WKSDetail.SPO_ID`` / ``PPO_ID`` are ``PODetail.PO_ID`` (the line
key). The line's ``PONumber`` then selects ``PO`` where ``Source`` is ``SO`` or
``PO``. ``PO.POID`` is never the worksheet line key: those integers collide.
"""

from __future__ import annotations

import html
from decimal import Decimal, InvalidOperation

from .limits import resolve_limit

MATERIAL_GL = "50100"
FREIGHT_GL = "50200"
HANDLING_GL = "50300"
EQUIPMENT_GL = "50600"
EXPENSE_GL = frozenset({HANDLING_GL, EQUIPMENT_GL})
# Source weight code S is a short ton: 2,000 lb. Odoo's ``uom.product_uom_ton``
# is the metric tonne (1,000 kg), so S is carried in pounds at this factor.
SHORT_TON_LB = 2000.0
_SHORT_TON = "S"
_POUND = "L"
# A ``Float`` field declared with ``digits`` is rounded on write
# (``odoo/orm/fields_numeric.py`` ``Float.convert_to_cache``); one declared
# without (Odoo 19 ``price_unit`` carries only ``min_display_digits``) keeps
# the full value. The source amount is compared against what the stored
# quantity and price reproduce, whichever way the target fields are declared.
_CENT = 0.005

__all__ = [
    "BASE_TRADE",
    "CARRIED_BY_PAYABLES",
    "CUSTOMER_CREDIT",
    "CUSTOMER_DEBIT",
    "DECLINED_PRICE_BASES",
    "DOMESTIC_SHIPPING_POINT_BASES",
    "EQUIPMENT_GL",
    "EXPENSE_GL",
    "FREIGHT_GL",
    "HANDLING_GL",
    "INCOTERM_BY_BASIS",
    "LINK_REASON_CLASSES",
    "MATERIAL_GL",
    "NOT_REALIZED",
    "PREPAY_OMITTED",
    "SETTLEMENT_EVIDENCE",
    "SHORT_TON_LB",
    "TRANSACTION_ONLY_COST",
    "UNAPPROVED",
    "UNBILLABLE",
    "WORKSHEET_SEPARATOR",
    "amount_drift",
    "clears_incoterm",
    "commission_recipients",
    "commission_slots",
    "declined_price_basis",
    "freight_vendor_id",
    "header_for_line",
    "incoterm_code",
    "ledger_adjustment_kind",
    "link_census",
    "link_reason_class",
    "native_quantity",
    "newest_numbers",
    "outside_universe_payables",
    "selected_worksheets",
    "payable_identity",
    "payable_matches_purchase",
    "payables_reconciliation",
    "purchase_bill_lines",
    "unit_priced_quantity",
    "zero_weight_exceptions",
    "quarantined_payable",
    "reconciliation_gap",
    "sale_note",
    "source_payable_identities",
    "with_worksheet",
    "worksheet_log",
    "worksheet_numbers",
    "worksheet_outcome",
    "unit_price",
    "vendor_bill_header_facts",
    "vendor_bill_due_terms",
    "worksheet_commission",
]


def header_for_line(index, line_key: str, source: str) -> tuple[dict | None, str]:
    """Return the single ``PO`` header for a worksheet line key, or a reason.

    A number that matches no header of the requested ``Source`` but does
    match the other one is named as such: that is a cross-linked line, which
    is a different source condition from a number no header carries at all.
    """
    if not line_key:
        return None, "blank line key"
    detail = index.order_lines.get(line_key)
    if not detail:
        return None, f"no order line for {line_key}"
    number = (detail.get("PONumber") or "").strip()
    if not number:
        return None, f"order line {line_key} has no PONumber"
    matches = index.orders_by_source_number.get((source, number), [])
    if len(matches) != 1:
        reason = f"{source} {number} matched {len(matches)} headers"
        other = "PO" if source == "SO" else "SO"
        if not matches and index.orders_by_source_number.get((other, number)):
            reason += f" (exists as {other})"
        return None, reason
    return index.orders[matches[0]], ""


# Root-cause classes of a worksheet line that resolves no native order header.
LINK_REASON_CLASSES = (
    "blank_key",
    "key_without_order_line",
    "order_line_without_number",
    "number_under_other_source",
    "number_without_header",
    "number_with_several_headers",
)


def link_reason_class(reason: str) -> str:
    """Classify a ``header_for_line`` reason by its source root cause."""
    text = (reason or "").strip()
    if text == "blank line key":
        return "blank_key"
    if text.startswith("no order line for "):
        return "key_without_order_line"
    if " has no PONumber" in text:
        return "order_line_without_number"
    if text.endswith(" headers (exists as SO)") or text.endswith(" headers (exists as PO)"):
        return "number_under_other_source"
    if " matched 0 headers" in text:
        return "number_without_header"
    if " matched " in text and " headers" in text:
        return "number_with_several_headers"
    return "other"


def link_census(index, failures: list[dict], worksheet_links: dict[str, dict[str, bool]]) -> dict:
    """Census of worksheet lines that resolved no order header, by side and root cause.

    ``failures`` carry ``number``, ``detail_id``, ``side`` (``sale`` or
    ``purchase``), ``key`` and ``reason``. ``worksheet_links`` says, per
    worksheet, whether any line resolved a sale header and a purchase header.
    Every figure is counted on source rows: a line is one ``DetailID``, a
    worksheet one ``BuySellNo``, an order reference one distinct key. The
    worksheet view says what the line view cannot: how many worksheets have
    no sale order at all, whether their purchase side still links, which
    financial documents the source holds for them, and the dollars involved.
    """
    groups: dict[tuple[str, str], dict] = {}
    for failure in failures:
        side = failure.get("side") or ""
        reason_class = link_reason_class(failure.get("reason") or "")
        group = groups.setdefault(
            (side, reason_class),
            {
                "side": side,
                "reason": reason_class,
                "lines": 0,
                "worksheets": set(),
                "keys": set(),
                "sale_amount": 0.0,
                "purchase_amount": 0.0,
            },
        )
        number = failure.get("number") or ""
        line = index.lines.get(failure.get("detail_id") or "", {})
        group["lines"] += 1
        group["worksheets"].add(number)
        if failure.get("key"):
            group["keys"].add(failure["key"])
        group["sale_amount"] += _number(line.get("SAmount"))
        group["purchase_amount"] += _number(line.get("PAmount"))

    by_reason = []
    for (_side, _reason), group in sorted(groups.items()):
        by_reason.append(
            {
                "side": group["side"],
                "reason": group["reason"],
                "lines": group["lines"],
                "worksheets": len(group["worksheets"]),
                "distinct_keys": len(group["keys"]),
                "sale_amount": round(group["sale_amount"], 2),
                "purchase_amount": round(group["purchase_amount"], 2),
            }
        )

    worksheets = {}
    for side in ("sale", "purchase"):
        unlinked = sorted(number for number, links in worksheet_links.items() if not links.get(side))
        worksheets[f"without_{side}_link"] = _worksheet_view(index, unlinked, worksheet_links, side)
    return {"lines_by_reason": by_reason, "worksheets": worksheets}


def _worksheet_view(index, numbers: list[str], worksheet_links: dict, side: str) -> dict:
    other = "purchase" if side == "sale" else "sale"
    view = {
        "worksheets": len(numbers),
        "lines": 0,
        f"with_{other}_link": 0,
        "with_customer_trade_ledger": 0,
        "with_customer_receipts": 0,
        "with_payables": 0,
        "partner_active": 0,
        "partner_inactive_or_absent": 0,
        "sale_amount": 0.0,
        "purchase_amount": 0.0,
        "years": {},
        "status": {},
        "numbers": numbers,
    }
    partner_column = "CustID" if side == "sale" else "VendorID"
    for number in numbers:
        detail_ids = index.lines_by_buysell.get(number, [])
        view["lines"] += len(detail_ids)
        for detail_id in detail_ids:
            line = index.lines.get(detail_id, {})
            view["sale_amount"] += _number(line.get("SAmount"))
            view["purchase_amount"] += _number(line.get("PAmount"))
        if worksheet_links.get(number, {}).get(other):
            view[f"with_{other}_link"] += 1
        ledger = index.ledger_by_buysell.get(number, [])
        if any((row.get("Source") or "").strip().upper() == "B" and _amount(row.get("Sale")) for row in ledger):
            view["with_customer_trade_ledger"] += 1
        if index.receipts_by_buysell.get(number):
            view["with_customer_receipts"] += 1
        if index.payables_by_buysell.get(number):
            view["with_payables"] += 1
        buysell = index.buysells.get(number, {})
        partner = (buysell.get(partner_column) or "").strip()
        if partner and (not index.counterparties or partner in index.counterparties):
            view["partner_active"] += 1
        else:
            view["partner_inactive_or_absent"] += 1
        year = (buysell.get("OrderDt") or "")[:4] or "unknown"
        view["years"][year] = view["years"].get(year, 0) + 1
        status = (buysell.get("status") or "").strip() or "blank"
        view["status"][status] = view["status"].get(status, 0) + 1
    view["sale_amount"] = round(view["sale_amount"], 2)
    view["purchase_amount"] = round(view["purchase_amount"], 2)
    view["years"] = dict(sorted(view["years"].items()))
    view["status"] = dict(sorted(view["status"].items()))
    return view


# Where a source payable row ended up when it was not written as a native bill.
TRANSACTION_ONLY_COST = "transaction_only_cost"  # amount carried on the transaction, no document
NOT_REALIZED = "not_realized"  # no account owner: nothing written, nothing counted
PREPAY_OMITTED = "prepay_omitted"  # historical vendor advance, excluded by rule
UNBILLABLE = "unbillable"  # account owner exists, but no vendor, journal, or amount


def quarantined_payable(row: dict, number: str, reason: str, disposition: str) -> dict:
    """One source bill the import did not realize, with everything needed to act on it.

    The row keeps its identity (``PayableID``), vendor, invoice reference,
    date, amount, GL lookup, batch and worksheet, plus the precise reason and
    where its amount went. Nothing here is a native document.
    """
    return {
        "payable_id": (row.get("PayableID") or "").strip(),
        "worksheet": number,
        "vendor": (row.get("CpID") or "").strip(),
        "invoice_no": (row.get("InvoiceNo") or "").strip(),
        "invoice_date": ((row.get("InvoiceDt") or "").strip())[:10],
        "amount": round(_amount(row.get("Amount")), 2),
        "gl": (row.get("GLAcct") or "").strip(),
        "batch": (row.get("APBatchNo") or "").strip(),
        "reason": reason,
        "disposition": disposition,
    }


def outside_universe_payables(index, numbers: list[str]) -> list[tuple[str, dict]]:
    """Payable rows whose ``BuySellNo`` is not a worksheet with lines.

    The transaction universe is every ``BuySellNo`` that owns a worksheet
    line. A payable outside it (a blank reference, or a free-text one such as
    ``51694 / 4714``) can be attached to no transaction, so the importer never
    visits it; it is returned here so every such row is reported, never
    silently omitted.
    """
    universe = set(numbers)
    found: list[tuple[str, dict]] = []
    for key in sorted(index.payables_by_buysell):
        if key in universe:
            continue
        found.extend((key, row) for row in index.payables_by_buysell[key])
    return found


def payable_identity(row: dict) -> str:
    """The source identity of a ``Payables`` row: its ``PayableID``. Blank when the source carries none."""
    return (row.get("PayableID") or "").strip()


def source_payable_identities(index) -> list[str]:
    """Every indexed payable row's identity, worksheet by worksheet, blanks included."""
    return [
        payable_identity(row) for key in sorted(index.payables_by_buysell) for row in index.payables_by_buysell[key]
    ]


def payables_reconciliation(
    expense_rows: list[tuple[str, str, float]],
    quarantine: list[dict],
    source_ids: list[str] | None = None,
    billed_ids: list[str] | tuple[str, ...] = (),
    excluded_ids: list[str] | tuple[str, ...] = (),
) -> dict:
    """Every indexed payable is a native bill, a quarantined row, or an explicit exclusion, exactly once.

    ``expense_rows`` carry ``(worksheet, bucket, amount)`` for every row the
    importer routed, including rows of worksheets it rolled back, refused for
    want of an order link, or found outside the worksheet universe; those
    rows are quarantined, so they sit on the quarantine side. The routed
    count closes only when the billed rows plus the quarantined rows account
    for every row seen.

    That count cannot see a row omitted from *both* sides, so the source is
    reconciled by identity as well: ``source_ids`` are the ``PayableID`` of
    every indexed row, ``billed_ids`` those written as native bills,
    ``excluded_ids`` those a diagnostic limit or a dry run deliberately left
    out, and the quarantine carries its own. A source identity on no side is
    ``missing``; one on two sides (or twice on one) is ``duplicated``; one the
    source does not carry is ``unknown``; a source row with no ``PayableID``
    cannot be proven covered and is counted in ``blank_identity_rows``. The
    reconciliation closes only when every list is empty, so an unrealized
    bill can never read as imported and a silent omission can never close.
    """
    kept = list(expense_rows)
    quarantined = list(quarantine)
    billed = [item for item in kept if item[1].endswith("_billed")]
    by_disposition: dict[str, dict] = {}
    for entry in quarantined:
        tally = by_disposition.setdefault(entry["disposition"], {"rows": 0, "amount": 0.0})
        tally["rows"] += 1
        tally["amount"] += entry["amount"]
    for tally in by_disposition.values():
        tally["amount"] = round(tally["amount"], 2)
    accounted: dict[str, int] = {}
    for identity in (*billed_ids, *(entry["payable_id"] for entry in quarantined), *excluded_ids):
        accounted[identity] = accounted.get(identity, 0) + 1
    duplicated = sorted(identity for identity, seen in accounted.items() if identity and seen > 1)
    excluded_rows = len(excluded_ids)
    if source_ids is None:
        source_rows = None
        blank_identity_rows = 0
        missing: list[str] = []
        unknown: list[str] = []
        unaccounted_rows = 0
    else:
        source = list(source_ids)
        source_rows = len(source)
        blank_identity_rows = sum(1 for identity in source if not identity)
        known = {identity for identity in source if identity}
        missing = sorted(known - set(accounted))
        unknown = sorted({identity for identity in accounted if identity} - known)
        unaccounted_rows = source_rows - len(billed) - len(quarantined) - excluded_rows
    return {
        "rows_seen": len(kept),
        "billed_rows": len(billed),
        "billed_amount": round(sum(item[2] for item in billed), 2),
        "quarantined_rows": len(quarantined),
        "quarantined_amount": round(sum(entry["amount"] for entry in quarantined), 2),
        "by_disposition": dict(sorted(by_disposition.items())),
        "source_rows": source_rows,
        "excluded_rows": excluded_rows,
        "unaccounted_rows": unaccounted_rows,
        "missing_rows": missing,
        "duplicated_rows": duplicated,
        "unknown_rows": unknown,
        "blank_identity_rows": blank_identity_rows,
        "closes": (
            len(kept) == len(billed) + len(quarantined)
            and unaccounted_rows == 0
            and not missing
            and not duplicated
            and not unknown
            and blank_identity_rows == 0
        ),
    }


def reconciliation_gap(reconciliation: dict, sample: int = 20) -> str:
    """Why a payables reconciliation does not close, naming the identities involved."""
    parts = []
    if reconciliation["rows_seen"] != reconciliation["billed_rows"] + reconciliation["quarantined_rows"]:
        parts.append(
            f"{reconciliation['rows_seen']} rows routed != {reconciliation['billed_rows']} billed"
            f" + {reconciliation['quarantined_rows']} quarantined"
        )
    if reconciliation.get("unaccounted_rows"):
        parts.append(
            f"{reconciliation['source_rows']} source rows != {reconciliation['billed_rows']} billed"
            f" + {reconciliation['quarantined_rows']} quarantined + {reconciliation['excluded_rows']} excluded"
        )
    for label in ("missing", "duplicated", "unknown"):
        identities = reconciliation.get(f"{label}_rows") or []
        if identities:
            shown = ", ".join(identities[:sample]) + (", …" if len(identities) > sample else "")
            parts.append(f"{len(identities)} {label} PayableID: {shown}")
    if reconciliation.get("blank_identity_rows"):
        parts.append(f"{reconciliation['blank_identity_rows']} source rows without a PayableID")
    return "; ".join(parts) or "closes"


def native_quantity(weight: str | None, uom_code: str | None) -> tuple[float, str]:
    """Source weight in a unit Odoo seeds. Short tons become pounds at 2,000 lb."""
    code = (uom_code or "").strip().upper()
    value = _number(weight)
    if code == _SHORT_TON:
        return value * SHORT_TON_LB, _POUND
    return value, code


def amount_drift(
    amount: str | None,
    quantity: float,
    price_unit: float,
    digits: int | None,
    quantity_digits: int | None = None,
) -> float:
    """Signed difference between the amount Odoo stores and the source amount.

    ``digits`` and ``quantity_digits`` are the storage precisions of the
    target ``price_unit`` and quantity fields (``None`` when the field is not
    rounded). The document line is ``stored quantity × stored price`` at two
    decimals; zero when that reproduces the source amount to the cent.
    """
    source = _number(amount)
    if not quantity:
        return 0.0
    stored_quantity = round(quantity, quantity_digits) if quantity_digits is not None else quantity
    stored_price = round(price_unit, digits) if digits is not None else price_unit
    stored = round(stored_quantity * stored_price, 2)
    drift = round(stored - source, 2)
    return drift if abs(drift) >= _CENT else 0.0


def newest_numbers(numbers: list[str], limit: int | None) -> list[str]:
    """The newest worksheet numbers when a diagnostic limit is set."""
    if not limit or limit >= len(numbers):
        return list(numbers)

    def _key(number: str) -> tuple[int, int | str]:
        return (0, int(number)) if number.isdigit() else (1, number)

    return sorted(numbers, key=_key)[-limit:]


# Worksheets kept in every limited import. 58699 carries the carrier freight
# chargeback for missing scale tickets; a newest-N cut would drop it.
PINNED_WORKSHEETS = ("58699",)


def selected_worksheets(numbers: list[str], limit: int | float | None) -> list[str]:
    """Newest worksheets, plus pinned numbers the source actually contains.

    ``limit`` is a worksheet count or a fraction of ``numbers`` (``0.25`` is the
    newest quarter). A fraction becomes a count here and nowhere else; an
    invalid limit raises before anything is selected.
    """
    selected = newest_numbers(numbers, resolve_limit(limit, len(numbers)))
    have = set(selected)
    available = set(numbers)
    for number in PINNED_WORKSHEETS:
        if number in available and number not in have:
            selected.append(number)
    return selected


def commission_slots(buysell: dict) -> list[dict]:
    """The two stored commission slots, as the worksheet carries them.

    The recipient is the raw ``ReferrerNo`` initials. A former representative
    keeps that identity here; the account reassignment table is for current
    partner ownership, not for history.
    """
    slots = []
    for slot in ("1", "2"):
        code = (buysell.get(f"ReferrerNo{slot}") or "").strip().upper()
        amount = _amount(buysell.get(f"Commission{slot}"))
        if code or amount:
            slots.append({"slot": slot, "code": code, "amount": amount})
    return slots


def worksheet_commission(buysell: dict) -> tuple[str, float, list[dict]]:
    """Stored recipient initials, the worksheet commission total, and the slots.

    The recipient is the slot that carries the amount. A named slot with no
    amount yields to a slot with one. When both slots name different people
    with an amount, slot 1 is the transaction salesperson and the slots are
    returned so the caller can record the second recipient.
    """
    slots = commission_slots(buysell)
    total = sum(slot["amount"] for slot in slots)
    chosen = ""
    for slot in slots:
        if slot["code"] and slot["amount"]:
            chosen = slot["code"]
            break
    if not chosen:
        for slot in slots:
            if slot["code"]:
                chosen = slot["code"]
                break
    return chosen, total, slots


def commission_recipients(slots: list[dict]) -> list[str]:
    """Distinct recipient initials across slots that carry an amount."""
    found: list[str] = []
    for slot in slots:
        code = slot["code"]
        if code and slot["amount"] and code not in found:
            found.append(code)
    return found


CUSTOMER_CREDIT = "customer_credit"
CUSTOMER_DEBIT = "customer_debit"
CARRIED_BY_PAYABLES = "carried_by_payables"
SETTLEMENT_EVIDENCE = "settlement_evidence"
UNAPPROVED = "unapproved"
BASE_TRADE = "base_trade"


def ledger_adjustment_kind(row: dict) -> str:
    """Route one ``GPLedger`` row.

    ``Source B`` is the base trade already carried by the worksheet lines.
    ``Source A`` + ``AdjType S`` approved is a customer credit (negative
    ``Sale``) or debit memo (positive). ``Source A`` + ``AdjType P`` is a
    vendor-side adjustment that ``Payables`` already carries as its own row.
    ``Source D`` and ``F`` are discount and fee rows taken at settlement.
    """
    source = (row.get("Source") or "").strip().upper()
    if source == "B":
        return BASE_TRADE
    if source in {"D", "F"}:
        return SETTLEMENT_EVIDENCE
    if (row.get("AdjApproved") or "").strip().upper() != "Y":
        return UNAPPROVED
    if (row.get("AdjType") or "").strip().upper() == "P":
        return CARRIED_BY_PAYABLES
    return CUSTOMER_CREDIT if _amount(row.get("Sale")) < 0 else CUSTOMER_DEBIT


WORKSHEET_SEPARATOR = ", "


def worksheet_numbers(origin: str | None) -> list[str]:
    """Worksheet numbers stored on a native order's ``origin``."""
    return [token.strip() for token in (origin or "").split(",") if token.strip()]


def with_worksheet(origin: str | None, number: str) -> str:
    """``origin`` with ``number`` added once, in worksheet order."""
    numbers = worksheet_numbers(origin)
    if number not in numbers:
        numbers.append(number)

    def _key(value: str) -> tuple[int, int | str]:
        return (0, int(value)) if value.isdigit() else (1, value)

    return WORKSHEET_SEPARATOR.join(sorted(numbers, key=_key))


def _amount(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def freight_vendor_id(rows) -> str:
    """Counterparty on the inland-freight expense row. A zero row is not a carrier."""
    chosen = ""
    for row in rows or []:
        if (row.get("GLAcct") or "").strip() != FREIGHT_GL:
            continue
        if not _amount(row.get("Cost")):
            continue
        vendor = (row.get("VendorID") or "").strip()
        if vendor:
            chosen = vendor
    return chosen


# Price bases with no Incoterm that means the same thing (BRS-EXP-02-R006,
# ADR-021 amendment 2026-11-12). ``delivered`` is not FAS (seller delivers
# alongside the ship), and neither DAP nor DDP is proven by the source: the
# order carries no Incoterm, and an Incoterm an earlier run wrote is cleared.
# The recycler's domestic shipping-point bases (``fob``, ``fob supplier dock``,
# ``pickup``: the buyer collects at the supplier's dock) are not the Incoterms
# 2020 FOB, which is delivery on board a vessel at the port of shipment. They
# set no Incoterm on a new order and never rewrite the Incoterm of an order
# already imported. Every declined basis is reported.
DOMESTIC_SHIPPING_POINT_BASES = frozenset({"fob", "fob supplier dock", "pickup"})
DECLINED_PRICE_BASES = frozenset({"delivered"}) | DOMESTIC_SHIPPING_POINT_BASES

# The only source basis that is the literal Incoterms 2020 rule of the same name.
INCOTERM_BY_BASIS = {"fas": "FAS"}


def incoterm_code(basis: str | None) -> str | None:
    """Map a source price basis onto an ``account.incoterms`` code."""
    text = (basis or "").strip().lower()
    if not text or "do not use" in text:
        return None
    return INCOTERM_BY_BASIS.get(text)


def declined_price_basis(basis: str | None) -> bool:
    """True when the basis is known and deliberately carries no Incoterm."""
    return (basis or "").strip().lower() in DECLINED_PRICE_BASES


def clears_incoterm(basis: str | None) -> bool:
    """True when a declined basis also clears an Incoterm an earlier run wrote.

    Only ``delivered`` does. A domestic shipping-point basis never rewrites an
    order already imported (ADR-021 amendment 2026-11-12).
    """
    text = (basis or "").strip().lower()
    return text in DECLINED_PRICE_BASES and text not in DOMESTIC_SHIPPING_POINT_BASES


def vendor_bill_header_facts(payable: dict, header: dict | None) -> dict[str, str]:
    """Invoice date, vendor invoice number, due date and terms for one ``Payables`` row.

    The bill stays one per ``PayableID``. Its header facts come from the
    row's ``PayablesBatch`` header when one is indexed, else from the row.
    There is no order-date fallback: a bill with no source invoice date has
    none. ``due_date`` and ``terms`` exist only on the header.
    """
    header = header or {}

    def first(*values) -> str:
        return next((text for value in values if (text := (value or "").strip())), "")

    return {
        "invoice_date": first(header.get("InvoiceDt"), payable.get("InvoiceDt"))[:10],
        "ref": first(header.get("InvoiceNo"), payable.get("InvoiceNo"), payable.get("PayableID")),
        "due_date": first(header.get("DueDate"))[:10],
        "terms": first(header.get("APTerms")),
    }


def vendor_bill_due_terms(facts: dict[str, str], term_id: int | None) -> dict:
    """``account.move`` values for the bill's payment term or explicit due date.

    A matched term applies only to a dated bill: Odoo computes a term from
    ``invoice_date or date or today``, so on an undated bill the due date
    would come from the day of the import. Without a usable term the header
    ``DueDate`` is the due date and no term is set, so the partner's default
    supplier term does not replace it. With neither, Odoo's default stays.
    """
    if term_id and facts.get("invoice_date"):
        return {"invoice_payment_term_id": term_id}
    if facts.get("due_date"):
        return {"invoice_payment_term_id": False, "invoice_date_due": facts["due_date"]}
    return {}


WORKSHEET_CANCELLED = "cancelled"


def worksheet_outcome(status: str | None) -> str:
    """Inventory-routing hint. Not the commercial transaction state.

    Source ``X`` still excludes a cancelled inventory inbound: no stock event
    and no commercial deal created from that exclusion. Every other code,
    including blank and unrecognized codes, is eligible for a Closed commercial
    transaction. The raw status is stored separately and is not a lifecycle.
    """
    code = (status or "").strip().upper()
    if code == "X":
        return WORKSHEET_CANCELLED
    return "closed"


def worksheet_log(problem: str | None, notes: str | None, booking: str | None = None) -> str:
    """Sticky note, speech bubble, then the booking text used as the logistics note."""
    parts = [part.strip() for part in (problem, notes, booking) if part and part.strip()]
    return "\n\n".join(parts)


def sale_note(problem: str | None, notes: str | None) -> str:
    """Sticky approval comment, a blank line, then the speech-bubble note."""
    sticky = (problem or "").strip()
    bubble = (notes or "").strip()
    if sticky and bubble:
        body = f"{html.escape(sticky)}<br/><br/>{html.escape(bubble)}"
    elif sticky or bubble:
        body = html.escape(sticky or bubble)
    else:
        return ""
    return f"<p>{body}</p>"


def unit_price(amount: str | None, weight: str | None, price: str | None) -> float:
    """``amount / weight`` when the weight is non-zero, otherwise the source price."""
    weight_value = _number(weight)
    if weight_value:
        return _number(amount) / weight_value
    return _number(price)


def _decimal(value) -> Decimal | None:
    """Exact source money. Blank and the extract's NULL token are zero. A bad token is None."""
    if isinstance(value, Decimal):
        return value
    text = "" if value is None else str(value).strip()
    if not text or text.upper() == "NULL":
        return Decimal(0)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def unit_priced_quantity(amount, price) -> tuple[str, Decimal | None, str]:
    """Integer each-quantity for a zero-weight line: ``amount / price``.

    ``WKSDetail.Units`` is not an input. Quantity 1 is not a substitute.
    Returns ``("empty", None, "")``, ``("unit", quantity, "")``, or
    ``("invalid", None, reason)``. ``quantity`` is the signed integer that
    reconciles: ``quantity * price == amount``.
    """
    amount_d = _decimal(amount)
    price_d = _decimal(price)
    if amount_d is None or price_d is None:
        return "invalid", None, "amount or unit price is not a decimal"
    if amount_d == 0:
        return "empty", None, ""
    if price_d == 0:
        return "invalid", None, "zero weight, nonzero amount, no unit price"
    quantity = amount_d / price_d
    if quantity != quantity.to_integral_value() or quantity * price_d != amount_d or quantity == 0:
        return "invalid", None, "amount is not an exact multiple of the unit price"
    return "unit", quantity, ""


def credit_line_terms(quantity: float, price: float) -> tuple[float, float]:
    """Positive quantity and price for one credit-note line.

    ``unit_priced_quantity`` keeps the source sign so ``quantity * price``
    still equals the source amount. A refund stores that magnitude; the move
    type carries the direction. A negative quantity with a positive price would
    otherwise leave a negative subtotal on an ``out_refund``.
    """
    return abs(float(quantity)), abs(float(price))


def zero_weight_exceptions(rows: list[dict], side: str) -> list[dict]:
    """Invalid zero-weight lines. Each row names the source identity, amount, and reason."""
    prefix = "S" if side == "sale" else "P"
    found = []
    for row in rows:
        weight, _uom = native_quantity(row.get(f"{prefix}Weight"), row.get(f"{prefix}WeightUOM"))
        if weight:
            continue
        kind, _quantity, reason = unit_priced_quantity(row.get(f"{prefix}Amount"), row.get(f"{prefix}Price"))
        if kind != "invalid":
            continue
        found.append(
            {
                "detail_id": (row.get("DetailID") or "").strip(),
                "side": side,
                "amount": "" if row.get(f"{prefix}Amount") is None else str(row.get(f"{prefix}Amount")).strip(),
                "reason": reason,
            }
        )
    return found


def purchase_bill_lines(rows: list[dict]) -> list[dict]:
    """Buy-side worksheet quantity and rate for a vendor bill.

    ``PWeight`` is the quantity. The rate is ``PAmount / PWeight``. A zero weight
    with a nonzero amount is an each-quantity only when ``PAmount / PPrice`` is
    an exact integer. Anything else is omitted here and reported by
    ``zero_weight_exceptions``. The payable lump is not a weight.
    """
    lines = []
    for row in rows:
        weight, uom = native_quantity(row.get("PWeight"), row.get("PWeightUOM"))
        if not weight:
            _kind, quantity, _reason = unit_priced_quantity(row.get("PAmount"), row.get("PPrice"))
            price_d = _decimal(row.get("PPrice"))
            if quantity is None or price_d is None:
                continue
            lines.append(
                {
                    "quantity": float(abs(quantity)),
                    "price_unit": float(abs(price_d)),
                    "uom": "E",
                    "grade": (row.get("GradeID") or "").strip(),
                    "description": (row.get("InvoiceDesc") or "").strip(),
                    "detail_id": (row.get("DetailID") or "").strip(),
                }
            )
            continue
        amount = _number(row.get("PAmount"))
        if not amount:
            continue
        lines.append(
            {
                "quantity": abs(weight),
                "price_unit": abs(amount) / abs(weight),
                "uom": uom,
                "grade": (row.get("GradeID") or "").strip(),
                "description": (row.get("InvoiceDesc") or "").strip(),
                "detail_id": (row.get("DetailID") or "").strip(),
            }
        )
    return lines


def payable_matches_purchase(payable_amount: float, rows: list[dict]) -> bool:
    """True when this payable is the worksheet purchase total, not a side charge."""
    total = sum(_number(row.get("PAmount")) for row in rows)
    return bool(total) and abs(abs(payable_amount) - abs(total)) < 0.02


def _number(value: str | None) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    return float(text)
