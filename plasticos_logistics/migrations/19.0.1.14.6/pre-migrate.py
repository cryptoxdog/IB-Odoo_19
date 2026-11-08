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
         WHERE t.load_id IS NOT NULL
           AND t.load_id IS DISTINCT FROM l.id
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


_MIGRATION_MARKER = "plasticos_logistics.load_parent_migration_done"


def _migration_done(cr):
    cr.execute("SELECT to_regclass('public.ir_config_parameter')")
    if cr.fetchone()[0] is None:
        return False
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (_MIGRATION_MARKER,))
    row = cr.fetchone()
    return bool(row and row[0] == "done")


def _mark_migration_done(cr):
    if _migration_done(cr):
        return
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES (%s, 'done', 1, 1, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
        """,
        (_MIGRATION_MARKER,),
    )


def _retire_singular_transaction_load_views(cr):
    """Drop stored transaction views that still call the removed singular load link.

    The form, its button, the list, and the search view are one inheritance chain.
    Loading either new view while the other still names ``load_id`` or
    ``action_view_load`` makes the upgrade fail. The current XML recreates them.
    """
    cr.execute("SELECT to_regclass('public.ir_ui_view'), to_regclass('public.ir_model_data')")
    view_table, data_table = cr.fetchone()
    if view_table is None or data_table is None:
        return
    singular_button = 'action_view_load\\"'
    singular_field = 'name=\\"load_id\\"'
    cr.execute(
        """
        SELECT v.id, d.id
          FROM ir_ui_view v
          JOIN ir_model_data d
            ON d.model = 'ir.ui.view'
           AND d.res_id = v.id
           AND d.module = 'plasticos_logistics'
         WHERE v.model = 'plasticos.transaction'
           AND (
                strpos(v.arch_db::text, %s) > 0
                OR strpos(v.arch_db::text, %s) > 0
           )
        """,
        (singular_button, singular_field),
    )
    rows = cr.fetchall()
    if not rows:
        return
    view_ids = [view_id for view_id, _data_id in rows]
    data_ids = [data_id for _view_id, data_id in rows]
    cr.execute("DELETE FROM ir_model_data WHERE id = ANY(%s)", (data_ids,))
    cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (view_ids,))
    _logger.info("plasticos_logistics pre-migrate retired %s singular transaction load views", len(view_ids))


def migrate(cr, version):
    if not version:
        return
    _retire_singular_transaction_load_views(cr)
    if _migration_done(cr):
        _logger.info("plasticos_logistics pre-migrate left current load parents unchanged")
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
