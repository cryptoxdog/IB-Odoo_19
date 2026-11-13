"""Copy each grade template's single color before color_id is dropped.

The relation is the template's only color field. This runs before the model
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
           AND table_name = 'plasticos_grade_template'
           AND column_name = 'color_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS plasticos_grade_template_color_rel (
            template_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            UNIQUE (template_id, color_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO plasticos_grade_template_color_rel (template_id, color_id)
        SELECT id, color_id
          FROM plasticos_grade_template
         WHERE color_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    _logger.info("Copied grade template colors into plasticos_grade_template_color_rel")
