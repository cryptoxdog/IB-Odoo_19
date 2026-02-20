"""Auto-geocode partners on create/write and nightly backfill.

This module extends ``res.partner`` to automatically call
``geo_localize()`` (provided by ``base_geolocalize``) whenever
a partner is created or its address fields change.

A nightly cron backfills any partners that still lack coordinates
(e.g. bulk imports, legacy data).
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Address fields that trigger re-geocoding when changed.
_ADDRESS_FIELDS = frozenset({
    "street", "street2", "city", "state_id",
    "zip", "country_id",
})


class ResPartnerGeo(models.Model):
    _inherit = "res.partner"

    # ─────────────────────────────────────────────────────────
    # CRUD Overrides
    # ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Geocode newly created partners that have an address."""
        partners = super().create(vals_list)
        to_geocode = partners.filtered(
            lambda p: p.street or p.city or p.zip
        )
        if to_geocode:
            try:
                to_geocode.geo_localize()
                _logger.info(
                    "Auto-geocoded %d new partner(s).", len(to_geocode),
                )
            except Exception:
                _logger.warning(
                    "Geocoding failed for new partner(s) %s. "
                    "Nightly cron will retry.",
                    to_geocode.ids,
                    exc_info=True,
                )
        return partners

    def write(self, vals):
        """Re-geocode when address fields change."""
        res = super().write(vals)
        if _ADDRESS_FIELDS & set(vals):
            to_geocode = self.filtered(
                lambda p: p.street or p.city or p.zip
            )
            if to_geocode:
                try:
                    to_geocode.geo_localize()
                    _logger.info(
                        "Re-geocoded %d partner(s) after address change.",
                        len(to_geocode),
                    )
                except Exception:
                    _logger.warning(
                        "Re-geocoding failed for partner(s) %s. "
                        "Nightly cron will retry.",
                        to_geocode.ids,
                        exc_info=True,
                    )
        return res

    # ─────────────────────────────────────────────────────────
    # Nightly Backfill Cron
    # ─────────────────────────────────────────────────────────

    @api.model
    def cron_geo_backfill(self):
        """Backfill coordinates for partners missing geo data.

        Runs nightly.  Processes in batches of 50 to respect
        geocoding API rate limits (Nominatim: 1 req/sec).
        """
        BATCH_SIZE = 50
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
        for partner in partners:
            try:
                partner.geo_localize()
                if partner.partner_latitude:
                    success += 1
            except Exception:
                _logger.warning(
                    "Geo backfill: failed for partner %s (%s).",
                    partner.id, partner.name,
                    exc_info=True,
                )

        _logger.info(
            "Geo backfill complete: %d/%d partners geocoded.",
            success, len(partners),
        )
