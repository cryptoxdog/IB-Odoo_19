"""Midnight recompute service for time-based stored computed fields.

Problem: Odoo's @api.depends can't depend on "time" — only field changes.
Fields like is_expired, days_open, is_overdue depend on "today" or "now"
but won't auto-update at midnight.

Solution: This cron runs at 00:05 daily and recomputes all time-sensitive
stored fields so they're accurate for the new day.

The cron stays here. Each higher-layer module extends this service with the
fields it owns:

- plasticos_documents: plasticos.document.is_expired
- plasticos_claims: plasticos.claim.days_open and is_overdue
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PlasticosMidnightRecompute(models.AbstractModel):
    """Midnight cron service for time-based field recomputation.

    NOTE: AbstractModel = no database table, no ACL needed.
    This is a service class, not a data model. Audit tools may flag
    "MISSING_ACL" but this is a false positive for AbstractModel classes.
    """

    _name = "plasticos.midnight.recompute"
    _description = "Midnight Recompute Service"

    @api.model
    def _cron_midnight_recompute(self):
        """Recompute all time-based stored fields at midnight.

        Uses advisory lock to prevent concurrent execution.
        """
        self.env.cr.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))",
            ["plasticos_base.cron_midnight_recompute"],
        )
        locked = self.env.cr.fetchone()[0]
        if not locked:
            _logger.info("Skipping midnight recompute: lock already held.")
            return

        try:
            self._recompute_document_expiry()
            self._recompute_claim_time_fields()
            _logger.info("Midnight recompute completed successfully.")
        finally:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(hashtext(%s))",
                ["plasticos_base.cron_midnight_recompute"],
            )

    def _recompute_document_expiry(self):
        """Extension point. Document expiry is implemented by plasticos_documents."""

    def _recompute_claim_time_fields(self):
        """Extension point. Claim time fields are implemented by plasticos_claims."""
