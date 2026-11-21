"""Move open document-review activities from the uploader to their routed owner.

Before 19.0.1.3.0 the review activity went to the file's owner. Since 19.0.1.3.3 the owner is
decided by the DEC-010 router (plasticos.exception.router) through the plasticos_base resolver;
the retired ``_manager_reviewer`` is no longer used. Open activities with this module's summary on
``documents.document`` are rerouted; an activity nobody eligible can take stays assigned and the
record is noted. A second run changes nothing.
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
    _logger.info("Document review activities rerouted: %s", result)
