"""Copy a location's coordinates onto its material profiles."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        UPDATE plasticos_material_profile AS profile
           SET lat = partner.partner_latitude,
               lon = partner.partner_longitude
          FROM res_partner AS partner
         WHERE profile.partner_id = partner.id
           AND (
                COALESCE(partner.partner_latitude, 0) <> 0
                OR COALESCE(partner.partner_longitude, 0) <> 0
           )
        """
    )
    _logger.info("Backfilled material profile coordinates from the location partner.")
