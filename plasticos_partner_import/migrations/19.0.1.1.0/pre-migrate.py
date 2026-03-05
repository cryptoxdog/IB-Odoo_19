"""Pre-migration: Rename x_private to is_private on plasticos_partner_bulk_update_wizard table.

Renames legacy Studio-style fields to clean module fields in plasticos_partner_import.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_ prefixed columns in plasticos_partner_import...")

    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'plasticos_partner_bulk_update_wizard'
          AND column_name = 'x_private'
        """
    )
    if cr.fetchone():
        cr.execute('ALTER TABLE plasticos_partner_bulk_update_wizard RENAME COLUMN "x_private" TO "is_private"')
        _logger.info("Renamed plasticos_partner_bulk_update_wizard.x_private -> is_private")
    else:
        _logger.debug("Column plasticos_partner_bulk_update_wizard.x_private not found, skipping")

    _logger.info("Partner import wizard column rename migration complete.")
