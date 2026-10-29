"""Project stored expiry and transaction compliance after the read-path repair.

Documents the previous midnight cron already stored as expired are projected
once here. The nightly domains only repair flag drift, so they skip that
history. Historical verification decisions, original bytes, and association
identity stay as they are. The same midnight projection then runs twice so a
replay is a no-op. Authorization continues to use the live read, not this
stored snapshot.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "plasticos.midnight.recompute" not in env or "plasticos.document" not in env:
        return
    service = env["plasticos.midnight.recompute"]
    document_model = env["plasticos.document"].with_context(active_test=False)
    today = document_model._evidence_today()
    historical = service._recompute_expiry_keyset(
        document_model,
        [
            ("expiry_date", "!=", False),
            ("expiry_date", "<", today),
            ("is_expired", "=", True),
        ],
    )
    service._recompute_document_expiry()
    service._recompute_document_expiry()
    _logger.info(
        "Document expiry projection migration %s finished. Historical expired rows projected: %s.",
        version,
        historical,
    )
