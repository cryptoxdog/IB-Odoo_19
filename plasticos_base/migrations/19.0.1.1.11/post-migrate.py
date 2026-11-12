"""Remove the retired attachment orphan cleanup cron from existing databases.

Version 19.0.1.1.11 removes ``ir.attachment._cron_cleanup_missing_filestore_orphans``
and its cron ``plasticos_base.ir_cron_cleanup_attachment_orphans``. That job deleted
``ir.attachment`` rows whose filestore file was missing, which also erased the record
that the file had been lost. Native Odoo keeps such rows: a missing file reads as
empty and is logged.

Odoo's end-of-upgrade cleanup skips a record whose xmlid has ``noupdate`` set, and
databases that first loaded this cron before 2026-03-17 carry ``noupdate = true`` on
it. So this script removes the cron itself. It finds the cron by xmlid and by code
that calls the retired method, archived crons included, and deletes each one with its
delegated server action. A cron that is running right now cannot be deleted; it is
deactivated and logged instead. The plasticos_base xmlids of the cron and of its
server action are removed in every case.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_METHOD = "_cron_cleanup_missing_filestore_orphans"
_CRON_XMLID = "ir_cron_cleanup_attachment_orphans"
_XMLIDS = (_CRON_XMLID, f"{_CRON_XMLID}_ir_actions_server")


def _xmlid_rows(env):
    return env["ir.model.data"].search([("module", "=", "plasticos_base"), ("name", "in", _XMLIDS)])


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {"active_test": False})
    Cron = env["ir.cron"]
    Action = env["ir.actions.server"]

    rows = _xmlid_rows(env)
    crons = Cron.browse(rows.filtered(lambda r: r.model == "ir.cron").mapped("res_id")).exists()
    crons |= Cron.search([("code", "like", _METHOD)])
    actions = Action.browse(rows.filtered(lambda r: r.model == "ir.actions.server").mapped("res_id")).exists()
    actions |= crons.ir_actions_server_id

    deleted, deactivated = [], []
    for cron in crons:
        try:
            with cr.savepoint():
                cron.unlink()
        except UserError:
            # The cron is running in another worker, so it is locked. This UPDATE
            # waits for that run to commit, then switches the cron off.
            cr.execute("UPDATE ir_cron SET active = false WHERE id = %s", (cron.id,))
            cron.invalidate_recordset(["active"])
            deactivated.append(cron.id)
            continue
        deleted.append(cron.id)

    removed_actions = []
    for action in actions.exists():
        if Cron.search_count([("ir_actions_server_id", "=", action.id)]):
            continue
        action.unlink()
        removed_actions.append(action.id)

    leftover = _xmlid_rows(env)
    leftover_ids = leftover.ids
    leftover.unlink()

    _logger.info(
        "plasticos_base 19.0.1.1.11: attachment orphan cleanup retired; "
        "deleted ir.cron %s, deleted ir.actions.server %s, removed ir.model.data %s",
        deleted,
        removed_actions,
        leftover_ids,
    )
    if deactivated:
        _logger.warning(
            "plasticos_base 19.0.1.1.11: ir.cron %s was running and could not be deleted; "
            "it is now inactive and has no plasticos_base xmlid. Delete it by hand.",
            deactivated,
        )
