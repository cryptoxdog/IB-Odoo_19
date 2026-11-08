"""Preserve loads_per_month when converting from stored computed float to integer."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE plasticos_material_profile
        SET loads_per_month = GREATEST(0, ROUND(COALESCE(loads_per_month, 0))::integer)
        WHERE loads_per_month IS NOT NULL
        """
    )
    _logger.info("Normalized loads_per_month values to integers.")

    cr.execute(
        """
        UPDATE plasticos_material_profile
        SET quantity_per_load_lbs = avg_lot_size_lbs
        WHERE (quantity_per_load_lbs IS NULL OR quantity_per_load_lbs = 0)
          AND avg_lot_size_lbs > 0
        """
    )
