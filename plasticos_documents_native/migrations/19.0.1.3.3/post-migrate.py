"""Move open association reviews and digitized-bill holds to their DEC-010 owner.

Before 19.0.1.3.3 every review went to the lowest-id Operations Manager as a generic to-do,
through ``_manager_reviewer`` (which did not exclude the cron user). The DEC-010 router now
decides: a classified original attributed to one record is Logistics work for shipping paperwork,
everything unattributed, unclassified, financial or blocked is the Operations Manager's. Each open
activity is retyped to its module-owned type and reassigned only when its owner is not valid for
its route. Before/after owner counts are logged. A second run changes nothing (POS-INV-19).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if "documents.document" not in env:
        return
    result = env["plasticos.document.sync"].reroute_open_reviews()
    _logger.info(
        "plasticos_documents_native 19.0.1.3.3: review owners before %s, after %s (%d rerouted)",
        result.before,
        result.after,
        result.rerouted,
    )
