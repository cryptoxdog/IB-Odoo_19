"""Nightly geocode backfill for partners."""

import logging
import time

from odoo import api, models

_logger = logging.getLogger(__name__)

_NOMINATIM_DELAY = 1.1
_FAILURE_DELAY = 5.0
_MAX_CONSECUTIVE_FAIL = 3
_BATCH_SIZE = 50


class ResPartnerGeo(models.Model):
    _inherit = "res.partner"

    @api.model
    def cron_geo_backfill(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_geolocalize.ir_cron_geo_backfill"])
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping geo backfill cron: lock is already held.")
            return

        try:
            partners = self.search(
                [
                    ("partner_latitude", "in", [0.0, False]),
                    "|",
                    ("street", "!=", False),
                    ("city", "!=", False),
                ],
                order="id ASC",
                limit=_BATCH_SIZE,
            )
            if not partners:
                return

            success = 0
            failed = 0
            consecutive_failures = 0
            for partner in partners:
                try:
                    partner.geo_localize()
                    if partner.partner_latitude:
                        success += 1
                        consecutive_failures = 0
                        self.env.cr.commit()  # pylint: disable=invalid-commit
                    time.sleep(_NOMINATIM_DELAY)
                except Exception:
                    failed += 1
                    consecutive_failures += 1
                    _logger.warning(
                        "Geo backfill: failed for partner %s (%s).", partner.id, partner.name, exc_info=True
                    )
                    if consecutive_failures >= _MAX_CONSECUTIVE_FAIL:
                        break
                    time.sleep(_FAILURE_DELAY)
            _logger.info("Geo backfill complete: %d/%d geocoded, %d failed.", success, len(partners), failed)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_geolocalize.ir_cron_geo_backfill"]
            )
