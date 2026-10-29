"""Copy historical transaction scale-ticket flags onto that transaction's one load."""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

_FLAG_CANDIDATES = {
    "scale_ticket_reminder_sent": ("scale_ticket_reminder_sent", "x_scale_ticket_reminder_sent"),
    "scale_ticket_escalated": ("scale_ticket_escalated", "x_scale_ticket_escalated"),
}


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


def _source_column(cr, names):
    for name in names:
        if _has_column(cr, "plasticos_transaction", name):
            return name
    return None


_FLAG_MARKER = "plasticos_documents.scale_ticket_historical_flags_copied"


def _marker_done(cr):
    cr.execute("SELECT to_regclass('public.ir_config_parameter')")
    if cr.fetchone()[0] is None:
        return False
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (_FLAG_MARKER,))
    row = cr.fetchone()
    return bool(row and row[0] == "done")


def _mark_done(cr):
    if _marker_done(cr):
        return
    cr.execute(
        """
        INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
        VALUES (%s, 'done', 1, 1, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
        """,
        (_FLAG_MARKER,),
    )


def migrate(cr, version):
    if not version:
        return
    if _marker_done(cr):
        _logger.info("plasticos_documents post-migrate left scale-ticket flags unchanged")
        return
    if not _has_column(cr, "plasticos_transaction", "load_id"):
        return
    if not _has_column(cr, "plasticos_load", "transaction_id"):
        _logger.info("plasticos_documents post-migrate waited for plasticos_load.transaction_id")
        return
    for target, sources in _FLAG_CANDIDATES.items():
        source = _source_column(cr, sources)
        if not source or not _has_column(cr, "plasticos_load", target):
            _logger.info("plasticos_documents post-migrate skipped %s; column not present", target)
            continue
        cr.execute(
            sql.SQL(
                """
                UPDATE plasticos_load AS l
                   SET {target} = TRUE
                  FROM plasticos_transaction AS t
                 WHERE l.transaction_id = t.id
                   AND t.{source} IS TRUE
                   AND l.{target} IS NOT TRUE
                """
            ).format(target=sql.Identifier(target), source=sql.Identifier(source))
        )
        _logger.info("plasticos_documents post-migrate copied %s %s flags", cr.rowcount, target)
    _mark_done(cr)
