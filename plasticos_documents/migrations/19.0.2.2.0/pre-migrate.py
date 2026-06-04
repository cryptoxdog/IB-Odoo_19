"""Pre-migration: Rename x_ prefixed columns on plasticos_transaction table.

This migration renames 8 columns in the plasticos_transaction table that were
originally created with the x_ (Studio/custom field) prefix convention.  The
Python field definitions already use the clean names, so the database columns
must be renamed *before* Odoo loads the new code to preserve existing data.

Additionally cleans up the stale ``x_document_ids`` entry from
``ir_model_fields`` so Odoo does not see a conflicting One2many definition
(the relationship is now defined in the bridge module).

Tables affected:
    plasticos_transaction — 8 column renames
    ir_model_fields       — 1 stale record deletion
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)


def _rename_columns(cr, table_name, renames):
    """Rename columns in a table if they exist (idempotent)."""
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
            _logger.info("Renamed %s.%s → %s", table_name, old_name, new_name)
        else:
            _logger.debug("Column %s.%s not found, skipping", table_name, old_name)


def migrate(cr, version):
    """Pre-migration entry point.

    Args:
        cr: Database cursor.
        version: Current module version string.
    """
    if not version:
        return

    _logger.info(
        "plasticos_documents: pre-migrate %s → 19.0.2.2.0  (transaction table column renames)",
        version,
    )

    # ── 1. Rename 8 columns on plasticos_transaction ──────────────
    _rename_columns(
        cr,
        "plasticos_transaction",
        [
            ("x_missing_doc_status", "missing_doc_status"),
            ("x_missing_supplier_docs", "missing_supplier_docs"),
            ("x_missing_carrier_docs", "missing_carrier_docs"),
            ("x_missing_buyer_docs", "missing_buyer_docs"),
            ("x_doc_reminder_count", "doc_reminder_count"),
            ("x_last_doc_reminder_date", "last_doc_reminder_date"),
            ("x_scale_ticket_reminder_sent", "scale_ticket_reminder_sent"),
            ("x_scale_ticket_escalated", "scale_ticket_escalated"),
        ],
    )

    # ── 2. Clean up stale x_document_ids metadata ─────────────────
    cr.execute(
        """
        DELETE FROM ir_model_fields
        WHERE model  = 'plasticos.transaction'
          AND name   = 'x_document_ids'
        """,
    )
    deleted = cr.rowcount
    if deleted:
        _logger.info(
            "Deleted %d stale ir_model_fields record(s) for x_document_ids",
            deleted,
        )
    else:
        _logger.debug("No stale x_document_ids metadata found, skipping")

    _logger.info("plasticos_documents: pre-migrate 19.0.2.2.0 complete")
