"""Pre-migration: Rename x_private to is_private on res_partner table.

Renames legacy Studio-style fields to clean module fields in plasticos_security_base.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_ prefixed columns in plasticos_security_base...")

    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_partner'
          AND column_name = 'x_private'
        """
    )
    if cr.fetchone():
        cr.execute('ALTER TABLE res_partner RENAME COLUMN "x_private" TO "is_private"')
        _logger.info("Renamed res_partner.x_private -> is_private")
    else:
        _logger.debug("Column res_partner.x_private not found, skipping")

    _logger.info("Security base column rename migration complete.")
