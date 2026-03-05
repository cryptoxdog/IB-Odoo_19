"""Pre-migration: Rename x_vanillasoft_id to vanillasoft_id on crm_lead.

Renames legacy Studio-style field to clean module field in plasticos_crm_bridge.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_vanillasoft_id to vanillasoft_id in plasticos_crm_bridge...")

    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'crm_lead'
          AND column_name = 'x_vanillasoft_id'
        """
    )
    if cr.fetchone():
        cr.execute('ALTER TABLE crm_lead RENAME COLUMN "x_vanillasoft_id" TO "vanillasoft_id"')
        _logger.info("Renamed crm_lead.x_vanillasoft_id -> vanillasoft_id")
    else:
        _logger.debug("Column crm_lead.x_vanillasoft_id not found, skipping")

    _logger.info("CRM bridge column rename migration complete.")
