"""Copy each intake's single color into the color relation before color_id is dropped.

The relation is the intake's only color field. This runs before the model
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
         WHERE table_schema = current_schema()
           AND table_name = 'plasticos_intake'
           AND column_name = 'color_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_intake_color_rel (
            intake_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            UNIQUE (intake_id, color_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO plasticos_intake_color_rel (intake_id, color_id)
        SELECT id, color_id
          FROM plasticos_intake
         WHERE color_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    _logger.info("Copied intake colors into plasticos_intake_color_rel")
