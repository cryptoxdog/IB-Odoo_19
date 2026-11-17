"""Drop the Linda request source check so the schedule purposes can be added.

Odoo recreates ``_check_exactly_one_source_order`` from the model on this
upgrade. The database name is ``{table}_{attribute}`` with the leading
underscore removed. A second run finds the new definition, which names
``booking_roll_request``, and drops nothing.
"""

import logging

_logger = logging.getLogger(__name__)

_TABLE = "plasticos_logistics_request"
_CONSTRAINT = "plasticos_logistics_request_check_exactly_one_source_order"


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass(%s)", ("public.plasticos_logistics_request",))
    if not cr.fetchone()[0]:
        _logger.info("plasticos_logistics 19.0.1.16.0 request check: table absent")
        return
    cr.execute(
        """
        SELECT conname
          FROM pg_constraint
         WHERE conrelid = %s::regclass
           AND contype = 'c'
           AND conname = %s
           AND pg_get_constraintdef(oid) LIKE %s
           AND pg_get_constraintdef(oid) NOT LIKE %s
        """,
        (_TABLE, _CONSTRAINT, "%booking_issue%", "%booking_roll_request%"),
    )
    found = cr.fetchone()
    if found:
        cr.execute(
            "ALTER TABLE plasticos_logistics_request "
            "DROP CONSTRAINT plasticos_logistics_request_check_exactly_one_source_order"
        )
    _logger.info(
        "plasticos_logistics 19.0.1.16.0 request check dropped %s",
        {"constraints_seen": 1 if found else 0, "constraints_dropped": 1 if found else 0},
    )
