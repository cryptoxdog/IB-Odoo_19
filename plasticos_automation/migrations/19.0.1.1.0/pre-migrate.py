"""Pre-migration: Rename x_ prefixed columns on automation tables.

Renames legacy Studio-style fields to clean module fields in plasticos_automation.
"""

import logging

from psycopg2 import sql

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
            cr.execute(
                sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO {}").format(
                    sql.Identifier(table_name),
                    sql.Identifier(old_name),
                    sql.Identifier(new_name),
                )
            )
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
            ("x_trucker_id", "carrier_id"),
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
            ("x_ready_for_pickup", "supplier_ready"),
            ("x_ready_confirmed_on", "ready_confirmed_on"),
            ("x_followup_count", "followup_count"),
            ("x_last_followup_on", "last_followup_on"),
            ("x_buyer_id", "buyer_id"),
        ],
    )

    # Sale Order (Approval & Delivery automation)
    _rename_columns(
        cr,
        "sale_order",
        [
            ("x_requires_approval", "requires_approval"),
            ("x_approved", "approved"),
            ("x_delivery_term", "delivery_term"),
            ("x_appt_requested", "appointment_requested"),
            ("x_appt_requested_on", "appointment_requested_on"),
        ],
    )

    # Res Partner (Contract renewal)
    _rename_columns(
        cr,
        "res_partner",
        [
            ("x_contract_end_date", "contract_end_date"),
        ],
    )

    # Account Move (Invoice reminder)
    _rename_columns(
        cr,
        "account_move",
        [
            ("x_last_reminder_date", "last_reminder_date"),
        ],
    )

    # Plasticos Load (SLA automation)
    _rename_columns(
        cr,
        "plasticos_load",
        [
            ("x_awaiting_ready_flag", "awaiting_ready_flag"),
            ("x_escalation_level", "escalation_level"),
        ],
    )

    # Product Product (Stock alert)
    _rename_columns(
        cr,
        "product_product",
        [
            ("x_min_stock_threshold", "min_stock_threshold"),
        ],
    )

    _logger.info("Automation column rename migration complete.")
