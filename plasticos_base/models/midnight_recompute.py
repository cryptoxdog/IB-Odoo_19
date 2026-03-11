"""Midnight recompute service for time-based stored computed fields.

Problem: Odoo's @api.depends can't depend on "time" — only field changes.
Fields like is_expired, days_open, is_overdue depend on "today" or "now"
but won't auto-update at midnight.

Solution: This cron runs at 00:05 daily and recomputes all time-sensitive
stored fields so they're accurate for the new day.

Fields handled:
- plasticos.document.is_expired
- plasticos.claim.days_open
- plasticos.claim.is_overdue
"""

import logging

from odoo import api, fields, models

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
        """Recompute is_expired for documents with expiry dates.

        Only touches documents where expiry status may have changed:
        - expiry_date <= today AND is_expired = False (newly expired)
        - expiry_date > today AND is_expired = True (incorrectly marked)
        """
        Document = self.env["plasticos.document"]
        if not Document:
            _logger.debug("plasticos.document not installed, skipping.")
            return

        today = fields.Date.today()

        # Find documents that should now be expired but aren't marked
        newly_expired = Document.search(
            [
                ("expiry_date", "<=", today),
                ("is_expired", "=", False),
                ("active", "=", True),
            ],
            order="id ASC",
            limit=1000,
        )
        if newly_expired:
            # Trigger recompute by calling the compute method
            newly_expired._compute_is_expired()
            _logger.info("Recomputed is_expired for %d newly expired documents.", len(newly_expired))

        # Find documents incorrectly marked as expired (edge case: expiry date extended)
        incorrectly_expired = Document.search(
            [
                ("expiry_date", ">", today),
                ("is_expired", "=", True),
                ("active", "=", True),
            ],
            order="id ASC",
            limit=1000,
        )
        if incorrectly_expired:
            incorrectly_expired._compute_is_expired()
            _logger.info("Corrected is_expired for %d documents.", len(incorrectly_expired))

    def _recompute_claim_time_fields(self):
        """Recompute days_open and is_overdue for active claims.

        Only touches claims that are still open (not resolved/archived).
        """
        Claim = self.env["plasticos.claim"]
        if not Claim:
            _logger.debug("plasticos.claim not installed, skipping.")
            return

        # Find all open claims
        open_claims = Claim.search(
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
