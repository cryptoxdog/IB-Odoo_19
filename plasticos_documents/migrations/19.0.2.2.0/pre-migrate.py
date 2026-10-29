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


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = %s
           AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cr.fetchone() is not None


def _columns_contradict(cr, table_name, old_name, new_name):
    cr.execute(
        sql.SQL(
            """
            SELECT 1
              FROM {}
             WHERE {} IS NOT NULL
               AND {} IS NOT NULL
               AND {} IS DISTINCT FROM {}
             LIMIT 1
            """
        ).format(
            sql.Identifier(table_name),
            sql.Identifier(old_name),
            sql.Identifier(new_name),
            sql.Identifier(old_name),
            sql.Identifier(new_name),
        )
    )
    return cr.fetchone() is not None


def _align_columns(cr, table_name, renames):
    """Rename, or merge when both columns exist. Refuse contradictory values first."""
    conflicts = []
    plan = []
    for old_name, new_name in renames:
        has_old = _column_exists(cr, table_name, old_name)
        has_new = _column_exists(cr, table_name, new_name)
        if has_old and has_new and _columns_contradict(cr, table_name, old_name, new_name):
            conflicts.append((old_name, new_name))
        else:
            plan.append((old_name, new_name, has_old, has_new))
    if conflicts:
        raise RuntimeError(
            f"plasticos_documents column rename refused contradictory values in {table_name}: {conflicts}"
        )
    for old_name, new_name, has_old, has_new in plan:
        if has_old and not has_new:
            cr.execute(
                sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO {}").format(
                    sql.Identifier(table_name),
                    sql.Identifier(old_name),
                    sql.Identifier(new_name),
                )
            )
            _logger.info("Renamed %s.%s to %s", table_name, old_name, new_name)
            continue
        if not (has_old and has_new):
            _logger.debug("Column %s.%s needs no change", table_name, old_name)
            continue
        cr.execute(
            sql.SQL("UPDATE {} SET {} = {} WHERE {} IS NULL AND {} IS NOT NULL").format(
                sql.Identifier(table_name),
                sql.Identifier(new_name),
                sql.Identifier(old_name),
                sql.Identifier(new_name),
                sql.Identifier(old_name),
            )
        )
        # Approved after the contradiction check and the copy into the destination column.
        # Rollback is the still-open transaction; a failed run does not commit the drop.
        # nosemgrep: plasticos-destructive-migration-sql-py
        cr.execute(
            sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(sql.Identifier(table_name), sql.Identifier(old_name))
        )
        _logger.info("Merged %s.%s into %s and dropped the source", table_name, old_name, new_name)


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

    # ── 1. Align renamed columns on plasticos_transaction ─────────
    _align_columns(
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
