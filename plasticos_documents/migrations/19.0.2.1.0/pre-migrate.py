"""Pre-migration: Rename x_ prefixed columns to standard names.

This migration removes the x_ prefix from custom fields that were incorrectly
named with the Studio/custom field convention.

Tables affected:
1. plasticos_document - 7 fields
2. plasticos_document_rule - 4 fields
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
            _logger.info("Renamed %s.%s → %s", table_name, old_name, new_name)
        else:
            _logger.debug("Column %s.%s not found, skipping", table_name, old_name)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_ prefixed columns...")

    # plasticos_document table
    _rename_columns(
        cr,
        "plasticos_document",
        [
            ("x_expiry_date", "expiry_date"),
            ("x_is_expired", "is_expired"),
            ("x_version", "version"),
            ("x_superseded_by", "superseded_by"),
            ("x_is_current", "is_current"),
            ("x_transaction_id", "transaction_id"),
            ("x_doc_category", "doc_category"),
        ],
    )

    # plasticos_document_rule table
    _rename_columns(
        cr,
        "plasticos_document_rule",
        [
            ("x_doc_category", "doc_category"),
            ("x_overdue_business_days", "overdue_business_days"),
            ("x_escalation_business_days", "escalation_business_days"),
            ("x_required_for_dispatch", "required_for_dispatch"),
        ],
    )

    _logger.info("Column rename migration complete.")
