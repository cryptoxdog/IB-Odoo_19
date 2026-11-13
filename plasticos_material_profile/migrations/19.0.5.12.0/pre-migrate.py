"""Copy each profile's single color into the color relation before color_id is dropped.

The relation is the profile's only color field. This runs before the model
update removes the old many-to-one column.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'plasticos_material_profile'
           AND column_name = 'color_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_material_profile_color_rel (
            profile_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            UNIQUE (profile_id, color_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO plasticos_material_profile_color_rel (profile_id, color_id)
        SELECT id, color_id
          FROM plasticos_material_profile
         WHERE color_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    _logger.info("Copied material profile colors into plasticos_material_profile_color_rel")
