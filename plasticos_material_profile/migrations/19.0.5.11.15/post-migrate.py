"""Backfill monthly volume as quantity per load times loads per month."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE plasticos_material_profile
           SET monthly_volume_lbs = COALESCE(quantity_per_load_lbs, 0) * COALESCE(loads_per_month, 0)
        """
    )
    _logger.info("Backfilled monthly_volume_lbs from quantity per load and loads per month.")
