"""Drop the Linda request source check so the schedule purposes can be added.

Odoo recreates ``_check_exactly_one_source_order`` from the model on this
upgrade. A second run finds nothing to drop.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

_TABLE = "plasticos_logistics_request"


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass(%s)", (f"public.{_TABLE}",))
    if not cr.fetchone()[0]:
        _logger.info("plasticos_logistics 19.0.1.16.0 request check: table absent")
        return
    cr.execute(
        """
        SELECT conname
          FROM pg_constraint
         WHERE conrelid = %s::regclass
           AND contype = 'c'
           AND pg_get_constraintdef(oid) LIKE %s
           AND pg_get_constraintdef(oid) NOT LIKE %s
        """,
        (_TABLE, "%booking_issue%", "%booking_roll_request%"),
    )
    names = [row[0] for row in cr.fetchall()]
    for name in names:
        cr.execute(sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(sql.Identifier(_TABLE), sql.Identifier(name)))
    _logger.info(
        "plasticos_logistics 19.0.1.16.0 request check dropped %s",
        {"constraints_seen": len(names), "constraints_dropped": len(names)},
    )
