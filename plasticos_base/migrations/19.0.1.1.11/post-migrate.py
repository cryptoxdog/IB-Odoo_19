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
delegated server action. The plasticos_base xmlids of the cron and of its server
action are removed in every case.

A cron that is running right now cannot be deleted. The script then tries to switch it
off; that UPDATE waits on the running job's row lock, up to the 15 s lock_timeout the
Odoo loader sets. If the lock is still held, the cron is left as it is and a WARNING
names it: the upgrade is never aborted. Once that run has ended, re-run this script from
an Odoo shell (``odoo shell -d <db>``); it finds the cron by its code:

    import importlib.util, os
    from odoo.modules import get_module_path
    path = os.path.join(get_module_path("plasticos_base"), "migrations", "19.0.1.1.11", "post-migrate.py")
    spec = importlib.util.spec_from_file_location("retire_attachment_cleanup", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    script.migrate(env.cr, "19.0.1.1.10")
    env.cr.commit()
"""

import logging

import psycopg2

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

    deleted, deactivated, locked = [], [], []
    for cron in crons:
        try:
            with cr.savepoint():
                cron.unlink()
            deleted.append(cron.id)
            continue
        except UserError:
            pass  # running in another worker: unlink refuses without waiting
        try:
            # Waits for that run to commit, up to the loader's lock_timeout.
            with cr.savepoint():
                cr.execute("UPDATE ir_cron SET active = false WHERE id = %s", (cron.id,))
            deactivated.append(cron.id)
        except psycopg2.OperationalError:
            locked.append(cron.id)
        cron.invalidate_recordset(["active"])

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
    if deactivated or locked:
        _logger.warning(
            "plasticos_base 19.0.1.1.11: ir.cron %s (deactivated) and %s (still active, row lock held) "
            "were running and could not be deleted, and now have no plasticos_base xmlid. Remove them "
            "once that run ends: re-run plasticos_base/migrations/19.0.1.1.11/post-migrate.py from an "
            "Odoo shell (see its docstring).",
            deactivated,
            locked,
        )
