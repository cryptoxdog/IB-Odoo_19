"""Move open document-review activities from the uploader to an Operations Manager.

Before 19.0.1.3.0 the review activity went to the file's owner. It now goes to
the deterministic manager reviewer. Only open activities with this module's
summary on ``documents.document`` whose assignee is not an Operations Manager
are moved. With no eligible manager nothing is moved and an error is logged.
A second run changes nothing.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

SUMMARY = "Document association needs review"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref("plasticos_security_base.group_operations_manager", raise_if_not_found=False)
    if not group or "documents.document" not in env:
        return
    managers = group.all_user_ids
    activities = env["mail.activity"].search(
        [("res_model", "=", "documents.document"), ("summary", "=", SUMMARY), ("user_id", "not in", managers.ids)]
    )
    service = env["plasticos.document.sync"]
    moved = 0
    for activity in activities:
        document = env["documents.document"].browse(activity.res_id).exists()
        reviewer = service._manager_reviewer(document.company_id if document else None)
        if not reviewer:
            _logger.error("No Operations Manager can take document review activity %s; it stays assigned.", activity.id)
            continue
        activity.write({"user_id": reviewer.id})
        moved += 1
    _logger.info("Reassigned %d of %d document review activities to an Operations Manager", moved, len(activities))
