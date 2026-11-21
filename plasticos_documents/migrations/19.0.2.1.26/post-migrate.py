"""Route pending evidence whose company cannot be resolved (DEC-005 d).

The stored ``evidence_company_id`` is computed for every row when the module is updated. A
pending row left without a company is hidden from every company-scoped user; this step gives each
one its single Operations activity on the original record. A second run changes nothing.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    unresolved = (
        env["plasticos.document"]
        .with_context(active_test=False)
        .search([("association_state", "!=", "accepted"), ("evidence_company_id", "=", False)])
    )
    unresolved._route_unresolved_company()
    _logger.info("Pending evidence with an unresolved company routed to Operations: %d rows", len(unresolved))
