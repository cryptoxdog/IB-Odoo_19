"""Claim half of the midnight recompute.

The cron itself stays on plasticos.midnight.recompute in plasticos_base.
This module owns plasticos.claim, so the claim lookup lives here.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PlasticosMidnightRecomputeClaim(models.AbstractModel):
    _inherit = "plasticos.midnight.recompute"

    def _recompute_claim_time_fields(self):
        """Recompute days_open and is_overdue for active claims.

        Only touches claims that are still open (not resolved/archived).
        """
        if "plasticos.claim" not in self.env:
            _logger.debug("plasticos.claim not installed, skipping.")
            return
        claim_model = self.env["plasticos.claim"]

        open_claims = claim_model.search(
            [
                ("state", "not in", ("resolved", "archived")),
            ],
            order="id ASC",
            limit=1000,
        )
        if open_claims:
            open_claims._compute_days_open()
            open_claims._compute_is_overdue()
            _logger.info("Recomputed time fields for %d open claims.", len(open_claims))
