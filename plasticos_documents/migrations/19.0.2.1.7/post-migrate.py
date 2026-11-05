"""Project stored expiry and transaction compliance after the read-path repair.

Historical verification decisions, original bytes, and association identity
stay as they are. The same midnight projection runs twice so a replay is a
no-op. Authorization continues to use the live read, not this stored snapshot.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "plasticos.midnight.recompute" not in env or "plasticos.document" not in env:
        return
    service = env["plasticos.midnight.recompute"]
    service._recompute_document_expiry()
    service._recompute_document_expiry()
    _logger.info("Document expiry projection migration %s finished.", version)
