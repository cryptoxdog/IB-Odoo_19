"""Pre-migration: Rename x_ prefixed columns on documents_document table.

Renames legacy Studio-style fields to clean module fields in plasticos_documents_native.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_ prefixed columns in plasticos_documents_native...")

    renames = [
        ("x_polymer_id", "polymer_id"),
        ("x_load_id", "load_id"),
        ("x_transaction_id", "transaction_id"),
        ("x_intake_id", "intake_id"),
        ("x_doc_type", "doc_type"),
        ("x_verified", "verified"),
        ("x_verified_by", "verified_by"),
        ("x_verified_at", "verified_at"),
        ("x_override", "override"),
        ("x_override_reason", "override_reason"),
        ("x_plasticos_doc_id", "plasticos_doc_id"),
    ]

    for old_name, new_name in renames:
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'documents_document'
              AND column_name = %s
            """,
            (old_name,),
        )
        if cr.fetchone():
            cr.execute(
                sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO {}").format(
                    sql.Identifier("documents_document"),
                    sql.Identifier(old_name),
                    sql.Identifier(new_name),
                )
            )
            _logger.info("Renamed documents_document.%s -> %s", old_name, new_name)
        else:
            _logger.debug("Column documents_document.%s not found, skipping", old_name)

    _logger.info("Documents native column rename migration complete.")
