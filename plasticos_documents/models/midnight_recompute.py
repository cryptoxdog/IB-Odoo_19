"""Document half of the midnight recompute.

The cron itself stays on plasticos.midnight.recompute in plasticos_base.
This module owns plasticos.document, so the document lookup lives here.
"""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PlasticosMidnightRecomputeDocument(models.AbstractModel):
    _inherit = "plasticos.midnight.recompute"

    def _recompute_document_expiry(self):
        """Recompute is_expired for documents with expiry dates.

        Only touches documents where expiry status may have changed:
        - expiry_date <= today AND is_expired = False (newly expired)
        - expiry_date > today AND is_expired = True (incorrectly marked)
        """
        if "plasticos.document" not in self.env:
            _logger.debug("plasticos.document not installed, skipping.")
            return
        document_model = self.env["plasticos.document"]

        today = fields.Date.today()

        newly_expired = document_model.search(
            [
                ("expiry_date", "<=", today),
                ("is_expired", "=", False),
                ("active", "=", True),
            ],
            order="id ASC",
            limit=1000,
        )
        if newly_expired:
            newly_expired._compute_is_expired()
            _logger.info("Recomputed is_expired for %d newly expired documents.", len(newly_expired))

        incorrectly_expired = document_model.search(
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
