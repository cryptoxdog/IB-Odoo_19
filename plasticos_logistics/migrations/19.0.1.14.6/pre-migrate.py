"""Copy plasticos.transaction.load_id onto plasticos.load.transaction_id.

Historical singular values are copied only when the stored parent is empty.
A disagreement stops the upgrade before any row changes.
"""

import logging

_logger = logging.getLogger(__name__)


def _has_column(cr, table, column):
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


def _conflicts(cr):
    conflicts = []
    cr.execute(
        """
        SELECT load_id, array_agg(id ORDER BY id)
          FROM plasticos_transaction
         WHERE load_id IS NOT NULL
         GROUP BY load_id
        HAVING count(*) > 1
        """
    )
    conflicts.extend(("duplicate_transaction_load_id", load_id, list(tx_ids)) for load_id, tx_ids in cr.fetchall())
    cr.execute(
        """
        SELECT t.id, t.load_id
          FROM plasticos_transaction t
         WHERE t.load_id IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM plasticos_load l WHERE l.id = t.load_id)
         ORDER BY t.id
        """
    )
    conflicts.extend(("missing_load", tx_id, load_id) for tx_id, load_id in cr.fetchall())
    if not _has_column(cr, "plasticos_load", "transaction_id"):
        return conflicts
    cr.execute(
        """
        SELECT t.id, t.load_id, l.transaction_id
          FROM plasticos_transaction t
          JOIN plasticos_load l ON l.id = t.load_id
         WHERE l.transaction_id IS NOT NULL
           AND l.transaction_id IS DISTINCT FROM t.id
         ORDER BY t.id
        """
    )
    conflicts.extend(
        ("load_parent_disagrees_with_transaction", tx_id, load_id, stored_tx)
        for tx_id, load_id, stored_tx in cr.fetchall()
    )
    cr.execute(
        """
        SELECT l.id, l.transaction_id, t.load_id
          FROM plasticos_load l
          JOIN plasticos_transaction t ON t.id = l.transaction_id
         WHERE t.load_id IS DISTINCT FROM l.id
         ORDER BY l.id
        """
    )
    conflicts.extend(
        ("stale_load_parent", load_id, stored_tx, tx_load) for load_id, stored_tx, tx_load in cr.fetchall()
    )
    cr.execute(
        """
        SELECT l.id, l.transaction_id
          FROM plasticos_load l
         WHERE l.transaction_id IS NOT NULL
           AND NOT EXISTS (
                SELECT 1 FROM plasticos_transaction t WHERE t.id = l.transaction_id
           )
         ORDER BY l.id
        """
    )
    conflicts.extend(("missing_parent_transaction", load_id, stored_tx) for load_id, stored_tx in cr.fetchall())
    return conflicts


def _copy(cr):
    if not _has_column(cr, "plasticos_load", "transaction_id"):
        return 0
    cr.execute(
        """
        UPDATE plasticos_load AS l
           SET transaction_id = t.id
          FROM plasticos_transaction AS t
         WHERE t.load_id = l.id
           AND l.transaction_id IS NULL
        """
    )
    return cr.rowcount


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.plasticos_transaction'), to_regclass('public.plasticos_load')")
    tx_table, load_table = cr.fetchone()
    if tx_table is None or load_table is None:
        return
    if not _has_column(cr, "plasticos_transaction", "load_id"):
        return
    conflicts = _conflicts(cr)
    if conflicts:
        raise RuntimeError(f"plasticos load parent migration refused. Resolve these rows before upgrading: {conflicts}")
    copied = _copy(cr)
    _logger.info("plasticos_logistics pre-migrate copied %s load parents", copied)
