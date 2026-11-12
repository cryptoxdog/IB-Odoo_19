"""Census and repair load companies before plasticos.load.company_id stops being related.

ADR-130 and the v2.7.5 M-LOG decision table. ``plasticos.load.company_id`` was a
stored related field of the sale order. It becomes an explicit source company.
Before the registry loads, every existing load is classified from its own
columns only:

* a load whose company agrees with its sources is kept unchanged;
* a load with no company and exactly one authoritative source company (its sale
  order, its parent transaction's sale order, or, with no sale order at all, its
  parent transaction's purchase orders) is repaired, and each repair is logged
  with the old value, the new value and the source;
* no source, or two sources that disagree, stops the whole upgrade before any
  row changes. Nothing is taken from ``env.company``, a default, or the user
  running the upgrade.

``19.0.1.14.6`` may run in the same upgrade, before this script. Until its post
step copies the old ``plasticos_transaction.load_id`` link, ``plasticos_load``
may have no ``transaction_id`` column; the transaction sources are then read
through that old column instead. Each load may have at most one parent
transaction (amendment A1); several parents for one load stop the upgrade.

The repair is idempotent: a second run finds no NULL company and changes
nothing. Its marker key is this script's own.
"""

import logging

_logger = logging.getLogger(__name__)

MIGRATION_MARKER = "plasticos_logistics.load_company_repair_19_0_1_14_20"


def has_column(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return cr.fetchone() is not None


def has_table(cr, table):
    cr.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    return cr.fetchone()[0] is not None


# Every statement below is a fixed literal. The two schema variants are handled
# by filling two temporary tables from fixed queries, never by composing SQL text.
_PARENT_FROM_LOAD = (
    "INSERT INTO plasticos_s2_census_parent (load_id, transaction_id) "
    "SELECT l.id, l.transaction_id FROM plasticos_load l WHERE l.transaction_id IS NOT NULL"
)
_PARENT_FROM_TRANSACTION = (
    "INSERT INTO plasticos_s2_census_parent (load_id, transaction_id) "
    "SELECT t.load_id, t.id FROM plasticos_transaction t WHERE t.load_id IS NOT NULL"
)


def _parent_link_sql(cr):
    """The fixed query that fills each load's parent link for this schema, or None.

    Before 19.0.1.14.6 the parent was ``plasticos_transaction.load_id``; from it on,
    ``plasticos_load.transaction_id``.
    """
    if has_column(cr, "plasticos_load", "transaction_id"):
        return _PARENT_FROM_LOAD
    if has_column(cr, "plasticos_transaction", "load_id"):
        return _PARENT_FROM_TRANSACTION
    return None


def _fill_census_tables(cr):
    """Fill the parent and source temporary tables. Writes nothing persistent."""
    # Session-local scratch tables; emptied before and after each census.
    cr.execute("CREATE TEMP TABLE IF NOT EXISTS plasticos_s2_census_parent (load_id integer, transaction_id integer)")
    cr.execute(
        "CREATE TEMP TABLE IF NOT EXISTS plasticos_s2_census_source (load_id integer, company_id integer, source varchar)"
    )
    cr.execute("DELETE FROM plasticos_s2_census_parent")
    cr.execute("DELETE FROM plasticos_s2_census_source")
    parent_insert = _parent_link_sql(cr)
    if parent_insert:
        cr.execute(parent_insert)
    cr.execute(
        """
        INSERT INTO plasticos_s2_census_source (load_id, company_id, source)
        SELECT l.id, so.company_id, 'sale_order'
          FROM plasticos_load l
          JOIN sale_order so ON so.id = l.sale_order_id
         WHERE so.company_id IS NOT NULL
        """
    )
    cr.execute(
        """
        INSERT INTO plasticos_s2_census_source (load_id, company_id, source)
        SELECT p.load_id, so.company_id, 'transaction_sale_order'
          FROM plasticos_s2_census_parent p
          JOIN plasticos_transaction t ON t.id = p.transaction_id
          JOIN sale_order so ON so.id = t.sale_order_id
         WHERE so.company_id IS NOT NULL
        """
    )
    # Default Many2many table of plasticos.transaction.purchase_order_ids.
    if has_table(cr, "plasticos_transaction_purchase_order_rel") and has_column(
        cr, "plasticos_transaction_purchase_order_rel", "plasticos_transaction_id"
    ):
        cr.execute(
            """
            INSERT INTO plasticos_s2_census_source (load_id, company_id, source)
            SELECT p.load_id, po.company_id, 'transaction_purchase_order'
              FROM plasticos_s2_census_parent p
              JOIN plasticos_load l ON l.id = p.load_id
              JOIN plasticos_transaction t ON t.id = p.transaction_id
              JOIN plasticos_transaction_purchase_order_rel rel ON rel.plasticos_transaction_id = t.id
              JOIN purchase_order po ON po.id = rel.purchase_order_id
             WHERE l.sale_order_id IS NULL
               AND t.sale_order_id IS NULL
               AND po.company_id IS NOT NULL
            """
        )


def census(cr):
    """Classify every load. Returns (repairs, refusals); writes nothing persistent.

    ``repairs`` is a list of (load_id, company_id, source); ``refusals`` a list
    of (load_id, reason, detail).
    """
    if not has_table(cr, "plasticos_load") or not has_column(cr, "plasticos_load", "company_id"):
        return [], []
    _fill_census_tables(cr)
    refusals = []
    cr.execute(
        """
        SELECT p.load_id, array_agg(DISTINCT p.transaction_id ORDER BY p.transaction_id)
          FROM plasticos_s2_census_parent p
         GROUP BY p.load_id
        HAVING count(DISTINCT p.transaction_id) > 1
        """
    )
    refusals.extend((load_id, "several_parent_transactions", list(tx_ids)) for load_id, tx_ids in cr.fetchall())
    cr.execute(
        """
        SELECT l.id,
               l.company_id,
               array_agg(DISTINCT s.company_id ORDER BY s.company_id)
                   FILTER (WHERE s.company_id IS NOT NULL),
               array_agg(DISTINCT s.source ORDER BY s.source) FILTER (WHERE s.source IS NOT NULL)
          FROM plasticos_load l
          LEFT JOIN plasticos_s2_census_source s ON s.load_id = l.id
         GROUP BY l.id, l.company_id
         ORDER BY l.id
        """
    )
    repairs = []
    for load_id, company_id, source_companies, source_names in cr.fetchall():
        source_companies = source_companies or []
        if len(source_companies) > 1:
            refusals.append((load_id, "conflicting_source_companies", source_companies))
            continue
        if company_id:
            if source_companies and source_companies[0] != company_id:
                refusals.append((load_id, "company_disagrees_with_source", [company_id, *source_companies]))
            continue
        if not source_companies:
            refusals.append((load_id, "no_source_company", []))
            continue
        repairs.append((load_id, source_companies[0], ",".join(source_names or [])))
    cr.execute("DELETE FROM plasticos_s2_census_parent")
    cr.execute("DELETE FROM plasticos_s2_census_source")
    return repairs, refusals


def migration_done(cr):
    if not has_table(cr, "ir_config_parameter"):
        return False
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (MIGRATION_MARKER,))
    row = cr.fetchone()
    return bool(row and row[0] == "done")


def mark_migration_done(cr):
    if migration_done(cr):
        return
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES (%s, 'done', 1, 1, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
        ON CONFLICT (key) DO UPDATE SET value = 'done'
        """,
        (MIGRATION_MARKER,),
    )


# What an operator does about each refusal, before rerunning the upgrade.
REMEDIES = {
    "no_source_company": (
        "attach its sale order, link it to a transaction backed by a purchase order of its company, "
        "or delete it if it is a stray draft"
    ),
    "conflicting_source_companies": (
        "its sale order and its parent transaction belong to different companies; correct the wrong link"
    ),
    "company_disagrees_with_source": "its stored company differs from its sale order or parent; correct one of them",
    "several_parent_transactions": "keep exactly one parent transaction for the load",
}
REFUSAL_LISTING_CAP = 20


def refusal_message(refusals, cap=REFUSAL_LISTING_CAP):
    """One line per reason: count, remedy, and at most ``cap`` load ids."""
    by_reason = {}
    for load_id, reason, detail in refusals:
        by_reason.setdefault(reason, []).append((load_id, detail))
    lines = ["plasticos load company migration refused. No row was changed."]
    for reason in sorted(by_reason):
        rows = by_reason[reason]
        shown = ", ".join(f"{load_id}{detail if detail else ''}" for load_id, detail in rows[:cap])
        more = f" and {len(rows) - cap} more" if len(rows) > cap else ""
        lines.append(
            f"- {reason} ({len(rows)} load(s)): {REMEDIES.get(reason, 'resolve the source')}. Loads: {shown}{more}."
        )
    return "\n".join(lines)


def migrate(cr, version):
    if not version:
        return
    repairs, refusals = census(cr)
    if refusals:
        raise RuntimeError(refusal_message(refusals))
    for load_id, company_id, source in repairs:
        cr.execute(
            "UPDATE plasticos_load SET company_id = %s WHERE id = %s AND company_id IS NULL",
            (company_id, load_id),
        )
        _logger.info(
            "plasticos_logistics pre-migrate repaired load %s company: NULL -> %s (source %s)",
            load_id,
            company_id,
            source,
        )
    _logger.info("plasticos_logistics pre-migrate load company census: %s repaired, 0 refused", len(repairs))
