"""Route existing Linda approvals by the DEC-011 authority table and give each pending one its activity.

The new ``routed_role`` column is filled with ``operations_manager`` by its default; rows whose
(command, edge case) is in ``LOGISTICS_AUTHORITY`` move to ``logistics_ops``. A pending row then
gets exactly one open activity for its owning role (searched before create). Idempotent: a
second run changes no row and schedules nothing. Counts are logged.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)
_VERSION = "19.0.1.17.0"


def migrate(cr, version):
    if not version:
        return
    from odoo.addons.plasticos_logistics.models.linda_approval import LOGISTICS_AUTHORITY, ROLE_LOGISTICS

    env = api.Environment(cr, SUPERUSER_ID, {})
    approvals = env["plasticos.linda.approval"].with_context(active_test=False)
    routed = 0
    for command, edge_case in sorted(LOGISTICS_AUTHORITY):
        cr.execute(
            """
            UPDATE plasticos_linda_approval
               SET routed_role = %s
             WHERE command = %s AND edge_case = %s AND routed_role IS DISTINCT FROM %s
               AND rerouted_at IS NULL
            """,
            (ROLE_LOGISTICS, command, edge_case, ROLE_LOGISTICS),
        )
        routed += cr.rowcount
    approvals.invalidate_model()
    pending = approvals.search([("state", "=", "pending")])
    pending._ensure_owner_activity()
    _logger.info(
        "plasticos_logistics %s Linda approvals: %s routed to Logistics Operations, %s pending checked for an activity",
        _VERSION,
        routed,
        len(pending),
    )
