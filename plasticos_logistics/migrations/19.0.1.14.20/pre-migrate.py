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


def _parent_link_sql(cr):
    """SQL yielding (load_id, transaction_id) for each load's parent, or None."""
    if has_column(cr, "plasticos_load", "transaction_id"):
        return "SELECT l.id AS load_id, l.transaction_id AS transaction_id FROM plasticos_load l"
    if has_column(cr, "plasticos_transaction", "load_id"):
        return "SELECT t.load_id AS load_id, t.id AS transaction_id FROM plasticos_transaction t"
    return None


def census(cr):
    """Classify every load. Returns (repairs, refusals); writes nothing.

    ``repairs`` is a list of (load_id, company_id, source); ``refusals`` a list
    of (load_id, reason, detail).
    """
    if not has_table(cr, "plasticos_load") or not has_column(cr, "plasticos_load", "company_id"):
        return [], []
    parent_sql = _parent_link_sql(cr)
    # Default Many2many table of plasticos.transaction.purchase_order_ids.
    has_po_link = has_table(cr, "plasticos_transaction_purchase_order_rel") and has_column(
        cr, "plasticos_transaction_purchase_order_rel", "plasticos_transaction_id"
    )
    # Each source contributes (load_id, company_id, source_name). The SQL is static;
    # only the parent-link subquery varies between two fixed literals above.
    sources = [
        """
        SELECT l.id, so.company_id, 'sale_order'
          FROM plasticos_load l
          JOIN sale_order so ON so.id = l.sale_order_id
         WHERE so.company_id IS NOT NULL
        """
    ]
    if parent_sql:
        sources.append(
            f"""
            SELECT p.load_id, so.company_id, 'transaction_sale_order'
              FROM ({parent_sql}) p
              JOIN plasticos_transaction t ON t.id = p.transaction_id
              JOIN sale_order so ON so.id = t.sale_order_id
             WHERE p.load_id IS NOT NULL
               AND so.company_id IS NOT NULL
            """  # noqa: S608 -- parent_sql is one of two static literals
        )
        if has_po_link:
            sources.append(
                f"""
                SELECT p.load_id, po.company_id, 'transaction_purchase_order'
                  FROM ({parent_sql}) p
                  JOIN plasticos_load l ON l.id = p.load_id
                  JOIN plasticos_transaction t ON t.id = p.transaction_id
                  JOIN plasticos_transaction_purchase_order_rel rel ON rel.plasticos_transaction_id = t.id
                  JOIN purchase_order po ON po.id = rel.purchase_order_id
                 WHERE p.load_id IS NOT NULL
                   AND l.sale_order_id IS NULL
                   AND t.sale_order_id IS NULL
                   AND po.company_id IS NOT NULL
                """  # noqa: S608 -- parent_sql is one of two static literals
            )
    refusals = []
    if parent_sql:
        cr.execute(
            f"""
            SELECT p.load_id, array_agg(DISTINCT p.transaction_id ORDER BY p.transaction_id)
              FROM ({parent_sql}) p
             WHERE p.load_id IS NOT NULL AND p.transaction_id IS NOT NULL
             GROUP BY p.load_id
            HAVING count(DISTINCT p.transaction_id) > 1
            """  # noqa: S608 -- parent_sql is one of two static literals
        )
        refusals.extend((load_id, "several_parent_transactions", list(tx_ids)) for load_id, tx_ids in cr.fetchall())
    union = " UNION ".join(sources)
    cr.execute(
        f"""
        SELECT l.id,
               l.company_id,
               array_agg(DISTINCT s.company_id ORDER BY s.company_id)
                   FILTER (WHERE s.company_id IS NOT NULL),
               array_agg(DISTINCT s.source ORDER BY s.source) FILTER (WHERE s.source IS NOT NULL)
          FROM plasticos_load l
          LEFT JOIN ({union}) AS s(load_id, company_id, source) ON s.load_id = l.id
         GROUP BY l.id, l.company_id
         ORDER BY l.id
        """  # noqa: S608 -- union is built only from the static literals above
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


def migrate(cr, version):
    if not version:
        return
    repairs, refusals = census(cr)
    if refusals:
        raise RuntimeError(
            "plasticos load company migration refused. No row was changed. Give each load one "
            f"authoritative source company before upgrading: {refusals}"
        )
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
