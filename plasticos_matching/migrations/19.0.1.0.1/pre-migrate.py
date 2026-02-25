"""Rename l9_* fields to generic names.

Migration: 19.0.1.0.0 → 19.0.1.0.1
- l9_run_id → run_id
- l9_model_version → model_version
- l9_timestamp → timestamp
- Update unique constraint
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Rename L9-specific columns to generic names."""
    if not version:
        return

    _logger.info("Migrating plasticos.match.result: renaming l9_* columns")

    # Rename columns
    renames = [
        ("l9_run_id", "run_id"),
        ("l9_model_version", "model_version"),
        ("l9_timestamp", "timestamp"),
    ]

    for old_name, new_name in renames:
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'plasticos_match_result'
              AND column_name = %s
            """,
            (old_name,),
        )
        if cr.fetchone():
            _logger.info("Renaming column %s → %s", old_name, new_name)
            cr.execute(f'ALTER TABLE plasticos_match_result RENAME COLUMN "{old_name}" TO "{new_name}"')
        else:
            _logger.info("Column %s does not exist, skipping", old_name)

    # Drop old constraint if exists
    cr.execute(
        """
        SELECT constraint_name
        FROM information_schema.table_constraints
        WHERE table_name = 'plasticos_match_result'
          AND constraint_name LIKE '%unique_match_per_run%'
        """
    )
    for (constraint_name,) in cr.fetchall():
        _logger.info("Dropping old constraint: %s", constraint_name)
        cr.execute(f'ALTER TABLE plasticos_match_result DROP CONSTRAINT IF EXISTS "{constraint_name}"')

    _logger.info("Migration complete")
