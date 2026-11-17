"""Choose a sale order's default delivery address from the customer's last order.

Pure selection logic, kept free of Odoo imports so it can be tested without a
registry. ``sale_order_inherit`` feeds it one batch of history rows read with a
single search and applies the result.

Operator decision (C1 lane C): a new order for a customer defaults its delivery
address to the one used on that customer's most recent non-cancelled order.
Only that most recent order is considered. When its delivery address is
archived, belongs to another commercial partner, or belongs to another company
than the new order, the native default (``address_get(['delivery'])``) applies.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryRow:
    """One prior sale order, newest first in the caller's ordering."""

    commercial_partner_id: int
    shipping_id: int
    shipping_active: bool
    shipping_commercial_partner_id: int
    shipping_company_id: int | None


def latest_row_per_customer(rows: Iterable[HistoryRow], wanted: Iterable[int]) -> dict[int, HistoryRow]:
    """Keep the first row seen for each wanted commercial partner (rows arrive newest first).

    Stops reading once every wanted customer has its newest row.
    """
    remaining = set(wanted)
    latest: dict[int, HistoryRow] = {}
    for row in rows:
        if row.commercial_partner_id not in remaining:
            continue
        latest[row.commercial_partner_id] = row
        remaining.discard(row.commercial_partner_id)
        if not remaining:
            break
    return latest


def last_used_delivery(
    commercial_partner_id: int,
    order_company_id: int | None,
    latest: dict[int, HistoryRow],
) -> int | None:
    """Return the last-used delivery address id, or None to keep the native default."""
    row = latest.get(commercial_partner_id)
    if row is None or not row.shipping_id or not row.shipping_active:
        return None
    if row.shipping_commercial_partner_id != commercial_partner_id:
        return None
    if row.shipping_company_id and order_company_id and row.shipping_company_id != order_company_id:
        return None
    return row.shipping_id
