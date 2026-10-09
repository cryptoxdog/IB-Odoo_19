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
    "EQUIPMENT_GL",
    "EXPENSE_GL",
    "FREIGHT_GL",
    "HANDLING_GL",
    "MATERIAL_GL",
    "freight_vendor_id",
    "header_for_line",
    "incoterm_code",
    "newest_numbers",
    "sale_note",
    "worksheet_log",
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


def worksheet_commission(buysell: dict) -> tuple[str, float]:
    """Stored salesperson initials and the sum of the worksheet commission slots.

    Slot 1 is the salesperson when it names someone. Slot 2 is used only when
    slot 1 is blank. The amount is the stored total, not a recomputed rate.
    """
    from .mapping import sales_rep_code  # noqa: PLC0415

    chosen = ""
    total = 0.0
    for slot in ("1", "2"):
        code = sales_rep_code(buysell.get(f"ReferrerNo{slot}"))
        total += _amount(buysell.get(f"Commission{slot}"))
        if code and not chosen:
            chosen = code
    return chosen, total


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


def _number(value: str | None) -> float:
    text = (value or "").strip()
    if not text:
        return 0.0
    return float(text)
