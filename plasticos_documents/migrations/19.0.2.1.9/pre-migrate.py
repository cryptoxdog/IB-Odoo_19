"""Refuse a scale-ticket flag whose historical load row is gone."""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

_FLAG_COLUMNS = (
    "scale_ticket_reminder_sent",
    "x_scale_ticket_reminder_sent",
    "scale_ticket_escalated",
    "x_scale_ticket_escalated",
)


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


def _flag_predicates(cr):
    predicates = []
    for name in _FLAG_COLUMNS:
        if _has_column(cr, "plasticos_transaction", name):
            predicates.append(sql.SQL("t.{} IS TRUE").format(sql.Identifier(name)))
    return predicates


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('public.plasticos_transaction')")
    if cr.fetchone()[0] is None or not _has_column(cr, "plasticos_transaction", "load_id"):
        return
    predicates = _flag_predicates(cr)
    if not predicates:
        return
    cr.execute(
        sql.SQL(
            """
            SELECT t.id, t.load_id
              FROM plasticos_transaction t
             WHERE t.load_id IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM plasticos_load l WHERE l.id = t.load_id)
               AND ({flags})
             ORDER BY t.id
            """
        ).format(flags=sql.SQL(" OR ").join(predicates))
    )
    conflicts = cr.fetchall()
    if conflicts:
        raise RuntimeError(
            f"plasticos scale-ticket flags point at missing loads. Resolve these transactions: {conflicts}"
        )
    _logger.info("plasticos_documents pre-migrate found no orphan scale-ticket flags")
