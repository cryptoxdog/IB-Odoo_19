"""Move open missing-document and scale-ticket escalations to their DEC-010 owner.

Before 19.0.2.1.24 every escalation went to an Operations Manager as a generic to-do. The
router now owns them: missing shipping paperwork only and a load's missing scale ticket go to
Logistics, anything financial or cross-department stays with the Operations Manager. Each open
activity is retyped to its module-owned type and reassigned only when its owner is not valid for
its route. The before/after owner counts are logged. A second run changes nothing (POS-INV-19).
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    result = env["plasticos.escalation.reroute"].reroute_open_escalations()
    _logger.info(
        "plasticos_documents 19.0.2.1.24: escalation owners before %s, after %s (%d rerouted)",
        result.before,
        result.after,
        result.rerouted,
    )
