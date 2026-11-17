"""Pickup and delivery dock-rule lookup. Odoo-free.

ADR-135 §3. The site's rule wins, then the commercial company's, then Appointment.
An empty rule is missing. The partner field's Appointment default counts as a rule
when the caller passes it. ``plan_copy`` is the same predicate the upgrade uses to
copy ``delivery_term`` into ``pickup_dock_rule``.
"""

from __future__ import annotations

APPOINTMENT = "appointment"
FCFS = "fcfs"
DOCK_RULE_VALUES = frozenset({FCFS, APPOINTMENT})
COPY_TABLES = frozenset({"plasticos_transaction", "purchase_order", "plasticos_load"})


def _known(value: str | None) -> str | None:
    if value in DOCK_RULE_VALUES:
        return value
    return None


def rule_from_site_then_company(
    site_rule: str | None,
    company_rule: str | None,
    *,
    partner_is_site: bool,
) -> str:
    """Site rule, else the commercial company's rule, else Appointment."""
    if partner_is_site:
        site = _known(site_rule)
        if site:
            return site
    company = _known(company_rule)
    if company:
        return company
    return APPOINTMENT


def plan_copy(rows: list[tuple[str | None, str | None]]) -> tuple[list[tuple[str | None, str | None]], dict[str, int]]:
    """Copy a missing pickup rule from the delivery rule. A second pass copies nothing.

    Each row is ``(delivery_term, pickup_dock_rule)``. A set pickup value is left
    alone, including on replay. The delivery value is never written.
    """
    copied = already_set = blank = 0
    planned: list[tuple[str | None, str | None]] = []
    for delivery, pickup in rows:
        if pickup is not None:
            already_set += 1
            planned.append((delivery, pickup))
        elif delivery is not None:
            copied += 1
            planned.append((delivery, delivery))
        else:
            blank += 1
            planned.append((delivery, pickup))
    return planned, {
        "rows_seen": len(rows),
        "rows_copied": copied,
        "already_set": already_set,
        "rows_blank": blank,
    }


def copy_pickup_dock_rule(cr, table: str) -> dict[str, int | str]:
    """Copy ``delivery_term`` into an empty ``pickup_dock_rule``. Idempotent.

    ``table`` is one of the three owned tables. A missing column reports skipped
    and writes nothing. Replay updates zero rows because the pickup column is set.
    """
    if table not in COPY_TABLES:
        raise ValueError(f"refusing dock-rule copy for {table}")
    if not _has_column(cr, table, "pickup_dock_rule") or not _has_column(cr, table, "delivery_term"):
        return {
            "table_name": table,
            "copy_status": "skipped",
            "rows_seen": 0,
            "rows_copied": 0,
            "already_set": 0,
            "rows_blank": 0,
        }
    # Each allowlisted table has its own statement. A table name is an identifier.
    count_sql = {
        "plasticos_transaction": """
            SELECT
                COUNT(*)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NOT NULL)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NULL AND delivery_term IS NULL)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NULL AND delivery_term IS NOT NULL)::integer
            FROM plasticos_transaction
            """,
        "purchase_order": """
            SELECT
                COUNT(*)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NOT NULL)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NULL AND delivery_term IS NULL)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NULL AND delivery_term IS NOT NULL)::integer
            FROM purchase_order
            """,
        "plasticos_load": """
            SELECT
                COUNT(*)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NOT NULL)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NULL AND delivery_term IS NULL)::integer,
                COUNT(*) FILTER (WHERE pickup_dock_rule IS NULL AND delivery_term IS NOT NULL)::integer
            FROM plasticos_load
            """,
    }[table]
    update_sql = {
        "plasticos_transaction": """
            UPDATE plasticos_transaction
               SET pickup_dock_rule = delivery_term
             WHERE pickup_dock_rule IS NULL
               AND delivery_term IS NOT NULL
            """,
        "purchase_order": """
            UPDATE purchase_order
               SET pickup_dock_rule = delivery_term
             WHERE pickup_dock_rule IS NULL
               AND delivery_term IS NOT NULL
            """,
        "plasticos_load": """
            UPDATE plasticos_load
               SET pickup_dock_rule = delivery_term
             WHERE pickup_dock_rule IS NULL
               AND delivery_term IS NOT NULL
            """,
    }[table]
    cr.execute(count_sql)
    seen, already_set, blank, pending = cr.fetchone()
    cr.execute(update_sql)
    return {
        "table_name": table,
        "copy_status": "copied",
        "rows_seen": seen,
        "rows_copied": cr.rowcount,
        "already_set": already_set,
        "rows_blank": blank,
        "rows_pending": pending,
    }


def _has_column(cr, table: str, column: str) -> bool:
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())
