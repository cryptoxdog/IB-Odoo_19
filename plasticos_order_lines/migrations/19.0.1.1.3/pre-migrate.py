"""Copy each order line's single color into its color relation before color_id is dropped.

The relation is the line's only color field. This runs before the model update
removes the old many-to-one column.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _copy_sale_colors(cr)
    _copy_purchase_colors(cr)


def _column_present(cr, table):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = 'color_id'
        """,
        (table,),
    )
    return bool(cr.fetchone())


def _copy_sale_colors(cr):
    if not _column_present(cr, "sale_order_line"):
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_line_color_rel (
            line_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            UNIQUE (line_id, color_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO sale_line_color_rel (line_id, color_id)
        SELECT id, color_id
          FROM sale_order_line
         WHERE color_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    _logger.info("Copied sale order line colors into sale_line_color_rel")


def _copy_purchase_colors(cr):
    if not _column_present(cr, "purchase_order_line"):
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_line_color_rel (
            line_id INTEGER NOT NULL,
            color_id INTEGER NOT NULL,
            UNIQUE (line_id, color_id)
        )
        """
    )
    cr.execute(
        """
        INSERT INTO purchase_line_color_rel (line_id, color_id)
        SELECT id, color_id
          FROM purchase_order_line
         WHERE color_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    _logger.info("Copied purchase order line colors into purchase_line_color_rel")
