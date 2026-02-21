"""Nightly geocode backfill for partners.

This module extends ``res.partner`` to geocode partners via a
nightly cron job. Auto-geocoding on create/write is DISABLED
to avoid rate-limiting issues with OpenStreetMap Nominatim
(strict 1 req/sec limit).

Partners created or updated will be geocoded by the nightly cron.
"""

import logging
import time

from odoo import api, models

_logger = logging.getLogger(__name__)

# Rate limit: OpenStreetMap Nominatim requires 1 request per second
_NOMINATIM_DELAY_SECONDS = 1.1


class ResPartnerGeo(models.Model):
    _inherit = "res.partner"

    # ─────────────────────────────────────────────────────────
    # NOTE: Auto-geocoding on create/write is DISABLED.
    # OpenStreetMap Nominatim has a strict 1 req/sec rate limit.
    # Bulk imports would trigger 429 Too Many Requests errors.
    # All geocoding is handled by the nightly cron with proper
    # rate limiting.
    # ─────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────
    # Nightly Backfill Cron
    # ─────────────────────────────────────────────────────────

    @api.model
    def cron_geo_backfill(self):
        """Backfill coordinates for partners missing geo data.

        Runs nightly. Processes in batches with rate limiting
        to respect Nominatim's 1 req/sec limit.
        """
        BATCH_SIZE = 100
        domain = [
            ("partner_latitude", "in", [0.0, False]),
            "|",
            ("street", "!=", False),
            ("city", "!=", False),
        ]
        partners = self.search(domain, limit=BATCH_SIZE)
        if not partners:
            _logger.info("Geo backfill: no partners need geocoding.")
            return

        success = 0
        failed = 0
        for partner in partners:
            try:
                partner.geo_localize()
                if partner.partner_latitude:
                    success += 1
                # Rate limit: wait between requests
                time.sleep(_NOMINATIM_DELAY_SECONDS)
            except Exception:
                failed += 1
                _logger.warning(
                    "Geo backfill: failed for partner %s (%s).",
                    partner.id, partner.name,
                    exc_info=True,
                )
                # Still rate limit on failure to avoid hammering API
                time.sleep(_NOMINATIM_DELAY_SECONDS)

        _logger.info(
            "Geo backfill complete: %d/%d partners geocoded, %d failed.",
            success, len(partners), failed,
        )
