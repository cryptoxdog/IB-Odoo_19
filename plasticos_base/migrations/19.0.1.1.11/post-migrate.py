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

A cron that is running right now cannot be deleted: ``unlink()`` refuses with a
``UserError`` when the job holds its row lock, and raises a serialization failure when
the job committed a change to that row after this transaction's REPEATABLE READ
snapshot. Both are caught. The script then switches the cron off with an UPDATE that
waits on the row lock, up to the 15 s lock_timeout the Odoo loader sets. If that UPDATE
succeeds, this transaction holds the row lock and ``unlink()`` is tried once more; the
cron stays inactive only if that also fails. If the UPDATE hits the lock timeout or a
serialization failure, the cron is left as it is. In both cases a WARNING names the
cron and the exception class, and the upgrade continues. Once that run has ended,
re-run this script from an Odoo shell (``odoo shell -d <db>``); it finds the cron by
its code:

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

import psycopg2.errors
from psycopg2.extensions import TransactionRollbackError

from odoo import SUPERUSER_ID, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_METHOD = "_cron_cleanup_missing_filestore_orphans"
_CRON_XMLID = "ir_cron_cleanup_attachment_orphans"
_XMLIDS = (_CRON_XMLID, f"{_CRON_XMLID}_ir_actions_server")


def _xmlid_rows(env):
    return env["ir.model.data"].search([("module", "=", "plasticos_base"), ("name", "in", _XMLIDS)])


def _unlink(cr, cron):
    """Delete ``cron``; return the exception class name when it is refused, else None."""
    try:
        with cr.savepoint():
            cron.unlink()
    except (UserError, TransactionRollbackError) as exc:
        return type(exc).__name__
    return None


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

    deleted, deactivated, left = [], {}, {}
    for cron in crons:
        refused = _unlink(cr, cron)
        if refused is None:
            deleted.append(cron.id)
            continue
        try:
            # Waits for the running job's row lock, up to the loader's lock_timeout.
            with cr.savepoint():
                cr.execute(
                    "UPDATE ir_cron SET active = false WHERE id = %s",
                    (cron.id,),
                    log_exceptions=False,
                )
        except (psycopg2.errors.LockNotAvailable, TransactionRollbackError) as exc:
            cron.invalidate_recordset(["active"])
            left[cron.id] = f"{refused}, then {type(exc).__name__}"
            continue
        cron.invalidate_recordset(["active"])
        # This transaction now holds the row lock, so the job has ended: try again.
        retry = _unlink(cr, cron)
        if retry is None:
            deleted.append(cron.id)
        else:
            deactivated[cron.id] = f"{refused}, then {retry}"

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
    if deactivated or left:
        _logger.warning(
            "plasticos_base 19.0.1.1.11: ir.cron could not be deleted while it was running and now has "
            "no plasticos_base xmlid; deactivated %s, left active %s (exception classes). Remove it once "
            "that run ends: re-run plasticos_base/migrations/19.0.1.1.11/post-migrate.py from an Odoo "
            "shell (see its docstring).",
            deactivated,
            left,
        )
