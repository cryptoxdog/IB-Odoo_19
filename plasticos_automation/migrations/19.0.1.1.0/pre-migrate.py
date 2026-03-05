"""Pre-migration: Rename x_ prefixed columns on stock_picking and purchase_order tables.

Renames legacy Studio-style fields to clean module fields in plasticos_automation.
"""

import logging

_logger = logging.getLogger(__name__)


def _rename_columns(cr, table_name, renames):
    """Rename columns in a table if they exist."""
    for old_name, new_name in renames:
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name = %s
            """,
            (table_name, old_name),
        )
        if cr.fetchone():
            cr.execute(f'ALTER TABLE {table_name} RENAME COLUMN "{old_name}" TO "{new_name}"')
            _logger.info("Renamed %s.%s -> %s", table_name, old_name, new_name)
        else:
            _logger.debug("Column %s.%s not found, skipping", table_name, old_name)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_ prefixed columns in plasticos_automation...")

    # Stock Picking (Trucker automation)
    _rename_columns(
        cr,
        "stock_picking",
        [
            ("x_trucker_id", "trucker_id"),
            ("x_receipt_confirmation", "receipt_confirmation"),
            ("x_trucker_notified_on", "trucker_notified_on"),
            ("x_trucker_followup_count", "trucker_followup_count"),
        ],
    )

    # Purchase Order (Supplier automation)
    _rename_columns(
        cr,
        "purchase_order",
        [
            ("x_ready_for_pickup", "ready_for_pickup"),
            ("x_ready_confirmed_on", "ready_confirmed_on"),
            ("x_followup_count", "followup_count"),
            ("x_last_followup_on", "last_followup_on"),
            ("x_buyer_id", "buyer_id"),
        ],
    )

    _logger.info("Automation column rename migration complete.")
