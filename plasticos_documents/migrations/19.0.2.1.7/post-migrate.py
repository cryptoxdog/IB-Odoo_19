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


def migrate(cr, version):
    if not version:
        return
    if not _has_column(cr, "plasticos_transaction", "load_id"):
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
                 WHERE t.load_id = l.id
                   AND t.{source} IS TRUE
                   AND l.{target} IS NOT TRUE
                   AND (l.transaction_id IS NULL OR l.transaction_id = t.id)
                """
            ).format(target=sql.Identifier(target), source=sql.Identifier(source))
        )
        _logger.info("plasticos_documents post-migrate copied %s %s flags", cr.rowcount, target)
