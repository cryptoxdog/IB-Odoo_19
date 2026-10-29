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

Statements are literals. The rename pairs are a closed list, so identifiers
are never composed into the query text.
"""

import logging

_logger = logging.getLogger(__name__)

# The probe pair is the regression fixture in test_scale_ticket_cardinality.
# It is not a production table.
_COLUMN_SQL = {
    (
        "plasticos_transaction",
        "x_missing_doc_status",
        "missing_doc_status",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_missing_doc_status IS NOT NULL
           AND missing_doc_status IS NOT NULL
           AND x_missing_doc_status IS DISTINCT FROM missing_doc_status
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_missing_doc_status TO missing_doc_status",
        """
        UPDATE plasticos_transaction
           SET missing_doc_status = x_missing_doc_status
         WHERE missing_doc_status IS NULL
           AND x_missing_doc_status IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_missing_doc_status",
    ),
    (
        "plasticos_transaction",
        "x_missing_supplier_docs",
        "missing_supplier_docs",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_missing_supplier_docs IS NOT NULL
           AND missing_supplier_docs IS NOT NULL
           AND x_missing_supplier_docs IS DISTINCT FROM missing_supplier_docs
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_missing_supplier_docs TO missing_supplier_docs",
        """
        UPDATE plasticos_transaction
           SET missing_supplier_docs = x_missing_supplier_docs
         WHERE missing_supplier_docs IS NULL
           AND x_missing_supplier_docs IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_missing_supplier_docs",
    ),
    (
        "plasticos_transaction",
        "x_missing_carrier_docs",
        "missing_carrier_docs",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_missing_carrier_docs IS NOT NULL
           AND missing_carrier_docs IS NOT NULL
           AND x_missing_carrier_docs IS DISTINCT FROM missing_carrier_docs
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_missing_carrier_docs TO missing_carrier_docs",
        """
        UPDATE plasticos_transaction
           SET missing_carrier_docs = x_missing_carrier_docs
         WHERE missing_carrier_docs IS NULL
           AND x_missing_carrier_docs IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_missing_carrier_docs",
    ),
    (
        "plasticos_transaction",
        "x_missing_buyer_docs",
        "missing_buyer_docs",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_missing_buyer_docs IS NOT NULL
           AND missing_buyer_docs IS NOT NULL
           AND x_missing_buyer_docs IS DISTINCT FROM missing_buyer_docs
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_missing_buyer_docs TO missing_buyer_docs",
        """
        UPDATE plasticos_transaction
           SET missing_buyer_docs = x_missing_buyer_docs
         WHERE missing_buyer_docs IS NULL
           AND x_missing_buyer_docs IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_missing_buyer_docs",
    ),
    (
        "plasticos_transaction",
        "x_doc_reminder_count",
        "doc_reminder_count",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_doc_reminder_count IS NOT NULL
           AND doc_reminder_count IS NOT NULL
           AND x_doc_reminder_count IS DISTINCT FROM doc_reminder_count
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_doc_reminder_count TO doc_reminder_count",
        """
        UPDATE plasticos_transaction
           SET doc_reminder_count = x_doc_reminder_count
         WHERE doc_reminder_count IS NULL
           AND x_doc_reminder_count IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_doc_reminder_count",
    ),
    (
        "plasticos_transaction",
        "x_last_doc_reminder_date",
        "last_doc_reminder_date",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_last_doc_reminder_date IS NOT NULL
           AND last_doc_reminder_date IS NOT NULL
           AND x_last_doc_reminder_date IS DISTINCT FROM last_doc_reminder_date
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_last_doc_reminder_date TO last_doc_reminder_date",
        """
        UPDATE plasticos_transaction
           SET last_doc_reminder_date = x_last_doc_reminder_date
         WHERE last_doc_reminder_date IS NULL
           AND x_last_doc_reminder_date IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_last_doc_reminder_date",
    ),
    (
        "plasticos_transaction",
        "x_scale_ticket_reminder_sent",
        "scale_ticket_reminder_sent",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_scale_ticket_reminder_sent IS NOT NULL
           AND scale_ticket_reminder_sent IS NOT NULL
           AND x_scale_ticket_reminder_sent IS DISTINCT FROM scale_ticket_reminder_sent
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_scale_ticket_reminder_sent TO scale_ticket_reminder_sent",
        """
        UPDATE plasticos_transaction
           SET scale_ticket_reminder_sent = x_scale_ticket_reminder_sent
         WHERE scale_ticket_reminder_sent IS NULL
           AND x_scale_ticket_reminder_sent IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_scale_ticket_reminder_sent",
    ),
    (
        "plasticos_transaction",
        "x_scale_ticket_escalated",
        "scale_ticket_escalated",
    ): (
        """
        SELECT 1
          FROM plasticos_transaction
         WHERE x_scale_ticket_escalated IS NOT NULL
           AND scale_ticket_escalated IS NOT NULL
           AND x_scale_ticket_escalated IS DISTINCT FROM scale_ticket_escalated
         LIMIT 1
        """,
        "ALTER TABLE plasticos_transaction RENAME COLUMN x_scale_ticket_escalated TO scale_ticket_escalated",
        """
        UPDATE plasticos_transaction
           SET scale_ticket_escalated = x_scale_ticket_escalated
         WHERE scale_ticket_escalated IS NULL
           AND x_scale_ticket_escalated IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_transaction DROP COLUMN x_scale_ticket_escalated",
    ),
    ("plasticos_column_align_probe", "old_flag", "new_flag"): (
        """
        SELECT 1
          FROM plasticos_column_align_probe
         WHERE old_flag IS NOT NULL
           AND new_flag IS NOT NULL
           AND old_flag IS DISTINCT FROM new_flag
         LIMIT 1
        """,
        "ALTER TABLE plasticos_column_align_probe RENAME COLUMN old_flag TO new_flag",
        """
        UPDATE plasticos_column_align_probe
           SET new_flag = old_flag
         WHERE new_flag IS NULL
           AND old_flag IS NOT NULL
        """,
        # nosemgrep: plasticos-destructive-migration-sql-py
        "ALTER TABLE plasticos_column_align_probe DROP COLUMN old_flag",
    ),
}


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


def _pair_sql(table_name, old_name, new_name):
    found = _COLUMN_SQL.get((table_name, old_name, new_name))
    if found is None:
        raise RuntimeError(f"plasticos_documents column rename refused an unexpected column {table_name}.{old_name}")
    return found


def _align_columns(cr, table_name, renames):
    """Rename, or merge when both columns exist. Refuse contradictory values first."""
    conflicts = []
    plan = []
    for old_name, new_name in renames:
        contradict_sql, rename_sql, merge_sql, drop_sql = _pair_sql(table_name, old_name, new_name)
        has_old = _column_exists(cr, table_name, old_name)
        has_new = _column_exists(cr, table_name, new_name)
        if has_old and has_new:
            cr.execute(contradict_sql)
            if cr.fetchone() is not None:
                conflicts.append((old_name, new_name))
                continue
        plan.append((old_name, new_name, has_old, has_new, rename_sql, merge_sql, drop_sql))
    if conflicts:
        raise RuntimeError(
            f"plasticos_documents column rename refused contradictory values in {table_name}: {conflicts}"
        )
    for old_name, new_name, has_old, has_new, rename_sql, merge_sql, drop_sql in plan:
        if has_old and not has_new:
            cr.execute(rename_sql)
            _logger.info("Renamed %s.%s to %s", table_name, old_name, new_name)
            continue
        if not (has_old and has_new):
            _logger.debug("Column %s.%s needs no change", table_name, old_name)
            continue
        cr.execute(merge_sql)
        # Approved after the contradiction check and the copy into the destination column.
        # Rollback is the still-open transaction; a failed run does not commit the drop.
        cr.execute(drop_sql)
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
