"""Copy each opportunity material row's single color before color_id is dropped.

The relation is the row's only color field. This runs before the model update
removes the old many-to-one column.
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
         WHERE table_schema = current_schema()
           AND table_name = 'plasticos_opportunity_material'
           AND column_name = 'color_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_opportunity_material_color_rel (
            material_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            UNIQUE (material_id, color_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO plasticos_opportunity_material_color_rel (material_id, color_id)
        SELECT id, color_id
          FROM plasticos_opportunity_material
         WHERE color_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    _logger.info("Copied opportunity material colors into plasticos_opportunity_material_color_rel")
