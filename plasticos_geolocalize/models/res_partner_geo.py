"""Nightly geocode backfill for partners."""

import json
import logging
import time

from odoo import api, models

_logger = logging.getLogger(__name__)

_LOG_PATH = "/Users/macm2/IB_Odoo-19 (MacMini)/IB-Odoo_19/.cursor/debug-75e499.log"
_SESSION = "75e499"


def _dbg(msg, data=None, hypothesis=None):
    import time as _t

    entry = {
        "sessionId": _SESSION,
        "location": "res_partner_geo.py",
        "message": msg,
        "data": data or {},
        "timestamp": int(_t.time() * 1000),
    }
    if hypothesis:
        entry["hypothesisId"] = hypothesis
    try:
        with open(_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: S110 -- best-effort debug sink; must never interrupt the geocode cron
        pass


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
                _logger.info("Geo backfill: no partners need geocoding.")
                return

            # #region agent log
            _dbg("batch start", {"partner_ids": partners.ids, "count": len(partners)}, "H-A")
            # #endregion

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
                except Exception as exc:
                    failed += 1
                    consecutive_failures += 1
                    # #region agent log
                    _dbg(
                        "geo_localize exception",
                        {
                            "partner_id": partner.id,
                            "partner_name": partner.name,
                            "street": partner.street,
                            "city": partner.city,
                            "zip": partner.zip,
                            "country": partner.country_id.name if partner.country_id else None,
                            "exc_type": type(exc).__name__,
                            "exc_msg": str(exc)[:300],
                            "consecutive": consecutive_failures,
                        },
                        "H-B" if "429" in str(exc) or "rate" in str(exc).lower() else "H-C",
                    )
                    # #endregion
                    _logger.warning(
                        "Geo backfill: failed for partner %s (%s).", partner.id, partner.name, exc_info=True
                    )
                    if consecutive_failures >= _MAX_CONSECUTIVE_FAIL:
                        # #region agent log
                        _dbg(
                            "aborting — consecutive failure limit reached",
                            {
                                "consecutive": consecutive_failures,
                                "last_partner_id": partner.id,
                                "last_exc": str(exc)[:300],
                            },
                            "H-A",
                        )
                        # #endregion
                        _logger.error(
                            "Geo backfill: %d consecutive failures — aborting (likely rate-limited or banned).",
                            consecutive_failures,
                        )
                        break
                    time.sleep(_FAILURE_DELAY)
            _logger.info("Geo backfill complete: %d/%d geocoded, %d failed.", success, len(partners), failed)
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))", ["plasticos_geolocalize.ir_cron_geo_backfill"]
            )
