"""Resolve worksheet lines onto native sale and purchase headers.

Odoo-free. ``WKSDetail.SPO_ID`` / ``PPO_ID`` are ``PODetail.PO_ID`` (the line
key). The line's ``PONumber`` then selects ``PO`` where ``Source`` is ``SO`` or
``PO``. ``PO.POID`` is never the worksheet line key: those integers collide.
"""

from __future__ import annotations

import html

MATERIAL_GL = "50100"
FREIGHT_GL = "50200"
HANDLING_GL = "50300"
EQUIPMENT_GL = "50600"
EXPENSE_GL = frozenset({HANDLING_GL, EQUIPMENT_GL})

__all__ = [
    "BASE_TRADE",
    "CARRIED_BY_PAYABLES",
    "CUSTOMER_CREDIT",
    "CUSTOMER_DEBIT",
    "EQUIPMENT_GL",
    "EXPENSE_GL",
    "FREIGHT_GL",
    "HANDLING_GL",
    "MATERIAL_GL",
    "SETTLEMENT_EVIDENCE",
    "UNAPPROVED",
    "WORKSHEET_SEPARATOR",
    "commission_recipients",
    "commission_slots",
    "freight_vendor_id",
    "header_for_line",
    "incoterm_code",
    "ledger_adjustment_kind",
    "newest_numbers",
    "selected_worksheets",
    "payable_matches_purchase",
    "purchase_bill_lines",
    "sale_note",
    "with_worksheet",
    "worksheet_log",
    "worksheet_numbers",
    "worksheet_outcome",
    "unit_price",
    "worksheet_commission",
]


def header_for_line(index, line_key: str, source: str) -> tuple[dict | None, str]:
    """Return the single ``PO`` header for a worksheet line key, or a reason."""
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
        return None, f"{source} {number} matched {len(matches)} headers"
    return index.orders[matches[0]], ""


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


def selected_worksheets(numbers: list[str], limit: int | None) -> list[str]:
    """Newest worksheets, plus pinned numbers the source actually contains."""
    selected = newest_numbers(numbers, limit)
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


def incoterm_code(basis: str | None) -> str | None:
    """Map a source price basis onto an ``account.incoterms`` code."""
    text = (basis or "").strip().lower()
    if not text or "do not use" in text:
        return None
    if text in {"fob", "fob supplier dock", "pickup"}:
        return "FOB"
    if text in {"delivered", "fas"}:
        return "FAS"
    return None


def worksheet_outcome(status: str | None) -> str:
    """Worksheet dropdown. WORK and NEW stay open. Invoiced stays closed."""
    code = (status or "").strip().upper()
    if code == "X":
        return "cancelled"
    if code in {"I", "C"}:
        return "closed"
    return "active"


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


def purchase_bill_lines(rows: list[dict]) -> list[dict]:
    """Buy-side worksheet quantity and rate for a vendor bill.

    ``PWeight`` is the quantity. The rate is ``PAmount / PWeight``. A stored
    price with no weight uses ``PAmount / PPrice`` as the quantity. The payable
    lump (one unit at the full amount) is not a weight.
    """
    lines = []
    for row in rows:
        amount = _number(row.get("PAmount"))
        weight = _number(row.get("PWeight"))
        price = _number(row.get("PPrice"))
        if not weight and amount and price:
            weight = amount / price
        if not weight or not amount:
            continue
        lines.append(
            {
                "quantity": abs(weight),
                "price_unit": abs(amount) / abs(weight),
                "uom": (row.get("PWeightUOM") or "").strip().upper(),
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
