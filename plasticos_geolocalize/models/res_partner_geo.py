"""Nightly geocode backfill for partners."""

import logging
import time

from odoo import api, models

_logger = logging.getLogger(__name__)

# Defaults; overridable at runtime via ir.config_parameter (see _geo_backfill_param).
_NOMINATIM_DELAY = 1.1
_FAILURE_DELAY = 5.0
_MAX_CONSECUTIVE_FAIL = 3
_BATCH_SIZE = 25


class ResPartnerGeo(models.Model):
    _inherit = "res.partner"

    @api.model
    def _geo_backfill_param(self, key, default, cast, minimum):
        """Read a geo-backfill tuning value from ir.config_parameter, fail-soft.

        Falls back to the module default on a missing or malformed value and
        clamps to a safe minimum (e.g. Nominatim's >=1 req/s usage policy).
        """
        # sudo: reading a global System Parameter from an unattended cron — no record-level data exposure.
        raw = self.env["ir.config_parameter"].sudo().get_param(key)
        if raw in (None, False, ""):
            return max(default, minimum)
        try:
            value = cast(raw)
        except (TypeError, ValueError):
            _logger.warning("Geo backfill: malformed %s=%r — falling back to default %s.", key, raw, default)
            value = default
        return max(value, minimum)

    @api.model
    def cron_geo_backfill(self):
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ["plasticos_geolocalize.ir_cron_geo_backfill"])
        if not self.env.cr.fetchone()[0]:
            _logger.info("Skipping geo backfill cron: lock is already held.")
            return

        try:
            nominatim_delay = self._geo_backfill_param(
                "plasticos_geolocalize.nominatim_delay", _NOMINATIM_DELAY, float, 1.0
            )
            failure_delay = self._geo_backfill_param("plasticos_geolocalize.failure_delay", _FAILURE_DELAY, float, 0.0)
            batch_size = self._geo_backfill_param("plasticos_geolocalize.batch_size", _BATCH_SIZE, int, 1)
            max_consecutive_failures = self._geo_backfill_param(
                "plasticos_geolocalize.max_consecutive_failures", _MAX_CONSECUTIVE_FAIL, int, 1
            )

            partners = self.search(
                [
                    ("partner_latitude", "in", [0.0, False]),
                    "|",
                    ("street", "!=", False),
                    ("city", "!=", False),
                ],
                order="id ASC",
                limit=batch_size,
            )
            if not partners:
                _logger.info("Geo backfill: no partners need geocoding.")
                return

            success = 0
            failed = 0
            consecutive_failures = 0
            # Nominatim usage policy: >=1 req/s (enforced via the nominatim_delay floor of 1.0s).
            # The User-Agent and geocoder provider are core-controlled (base_geolocalize); a durable
            # fix for a persistent 429 is a keyed provider — tracked as a separate follow-up GMP.
            for partner in partners:
                try:
                    partner.geo_localize()
                    if partner.partner_latitude:
                        success += 1
                        consecutive_failures = 0
                        self.env.cr.commit()  # pylint: disable=invalid-commit
                    time.sleep(nominatim_delay)
                except Exception:
                    failed += 1
                    consecutive_failures += 1
                    _logger.warning(
                        "Geo backfill: failed for partner %s (%s).", partner.id, partner.name, exc_info=True
                    )
                    if consecutive_failures >= max_consecutive_failures:
                        _logger.error(
                            "Geo backfill: %d consecutive failures — aborting (likely rate-limited or banned).",
                            consecutive_failures,
                        )
                        break
                    time.sleep(failure_delay)
            _logger.info("Geo backfill complete: %d/%d geocoded, %d failed.", success, len(partners), failed)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_geolocalize.ir_cron_geo_backfill"]
            )
