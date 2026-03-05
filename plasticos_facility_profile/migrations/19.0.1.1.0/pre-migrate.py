"""Pre-migration: Rename x_ prefixed columns on res_partner table.

Renames legacy Studio-style fields to clean module fields in plasticos_facility_profile.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    _logger.info("Renaming x_ prefixed columns in plasticos_facility_profile...")

    renames = [
        ("x_facility_role", "facility_role"),
        ("x_preferred_contact_id", "preferred_contact_id"),
    ]

    for old_name, new_name in renames:
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'res_partner'
              AND column_name = %s
            """,
            (old_name,),
        )
        if cr.fetchone():
            cr.execute(f'ALTER TABLE res_partner RENAME COLUMN "{old_name}" TO "{new_name}"')
            _logger.info("Renamed res_partner.%s -> %s", old_name, new_name)
        else:
            _logger.debug("Column res_partner.%s not found, skipping", old_name)

    _logger.info("Facility profile column rename migration complete.")
