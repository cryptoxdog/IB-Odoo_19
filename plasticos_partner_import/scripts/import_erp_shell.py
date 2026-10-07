"""Odoo-shell driver for ``make import-erp``.

Executed inside ``odoo shell`` against the target database (Makefile pipes this
file into the shell). Configuration arrives via environment variables so the
single file serves both the docker and the no-Docker harness paths:

* ``ERP_DRY`` — ``1`` for a resolve-and-map preview (nothing persisted)
* ``ERP_LIMIT`` — process at most N transactions (diagnostics)
* ``ERP_PAYLOAD_ROOT`` — non-default payload directory (statement or grid form)
* ``ERP_SQL_SERVER`` / ``ERP_SQL_DATABASE`` (+ ``ERP_SQL_USER`` /
  ``ERP_SQL_PASSWORD`` / ``ERP_SQL_PORT`` / ``ERP_SQL_DRIVER``) — read the
  requested partner and/or transaction-reconstruction tables directly from
  the restored ERP database through ``PROJECTION_SCRIPTS`` (ADR-021). Takes
  precedence over ``ERP_PAYLOAD_ROOT``.
* ``ERP_REPORT_PATH`` — write the machine-readable summary JSON here
* ``ERP_TARGET_DB`` — the disposable database this run may write; the
  database check refuses any other database and any production database
* ``ERP_PARTNERS_ONLY`` — ``1`` imports only CounterParty, Address, Contact,
  ContactRoleAssignment, and SalesReps (Concern 1). The six deal tables are
  not opened. Without this flag, a full run also reads Payables, Receipt,
  ReceiptBatch, GPLedger, WKSDetail, and WksDelivery and must reach the
  ``plasticos_transaction`` historical-import extension.
* ``ERP_LAYER`` — ``counterparties``, ``addresses``, ``contacts``, ``roles``,
  or ``salesreps``. Only that table is read, and only after the previous
  layer's validator passes.
* ``ERP_REQUIRE_EMPTY`` — ``0`` allows a database that already has business
  partners. Any other value (including unset) refuses a full import or the
  ``counterparties`` layer unless the only ``res.partner`` rows are the company
  and the login users.

Order of operations for an applied run: database check → (layer mode) the
previous layer's check → import each stage → that stage's validator → commit.
A validator that fails raises before the commit, the transaction is rolled
back, and nothing of the run is persisted. Dry runs validate nothing and
always exit 0. Exit code is otherwise nonzero when a validator fails or the
summary reports ``failed``, so the Makefile target fails closed.
"""

import os
import sys

from odoo.addons.plasticos_partner_import.erp import reader
from odoo.addons.plasticos_partner_import.scripts.run_erp_import import run
from odoo.addons.plasticos_partner_import.scripts.validate_partner_layer import (
    DATABASE_CHECK,
    LAYER_BEFORE,
    LayerRejected,
    validate,
)


def _setting(name: str) -> str:
    return os.environ.get(f"ERP_{name}") or ""


def _flag(name: str) -> bool:
    return _setting(name).strip().lower() in {"1", "true", "yes", "y"}


def _odoo_env():
    """The Odoo environment injected by ``odoo shell`` stdin execution."""
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return env


def _require_empty_partner_set(env) -> None:
    """Refuse the import when the database already has business partners.

    A usable database always has the company partner and one partner per user.
    Those are the only rows allowed before a test import.
    """
    if _setting("REQUIRE_EMPTY").strip().lower() in {"0", "false", "no", "n"}:
        return
    # Direct SQL justification: a whole-table census before a bulk load; the ORM would browse every partner.
    env.cr.execute(
        """
        SELECT count(*)
          FROM res_partner
         WHERE id NOT IN (
                SELECT partner_id FROM res_users WHERE partner_id IS NOT NULL
                UNION
                SELECT partner_id FROM res_company WHERE partner_id IS NOT NULL
               )
        """
    )
    extra = int(env.cr.fetchone()[0])
    # Direct SQL justification: same bulk census, total rows including archived partners.
    env.cr.execute("SELECT count(*) FROM res_partner")
    total = int(env.cr.fetchone()[0])
    print(f"res.partner before import: {total} (outside company and users: {extra})")
    if extra:
        raise SystemExit(
            "refusing import: database still has res.partner rows that are not the company or a login user"
        )


def main() -> int:
    limit_raw = _setting("LIMIT").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else None
    env = _odoo_env()
    dry_run = _flag("DRY")
    layer = _setting("LAYER").strip().lower() or None
    if layer and layer not in LAYER_BEFORE:
        raise SystemExit(f"ERP_LAYER must be one of {', '.join(LAYER_BEFORE)}")
    database = reader.database_source_from_env(os.environ)
    if database is not None:
        print(f"ERP source: direct database read ({database.label})")

    if not dry_run:
        if validate(env, DATABASE_CHECK):
            print("refusing import: the database check did not pass")
            return 1
        if layer and LAYER_BEFORE[layer] != DATABASE_CHECK and validate(env, LAYER_BEFORE[layer]):
            print(f"refusing layer {layer}: the {LAYER_BEFORE[layer]} validator did not pass")
            return 1
        if layer in (None, "counterparties"):
            _require_empty_partner_set(env)

    def after_stage(name: str, payload) -> None:
        """Validate the stage just written against the rows it read. Raise before any commit."""
        if validate(env, name, payload=payload):
            raise LayerRejected(name)

    try:
        result = run(
            env,
            payload_root=_setting("PAYLOAD_ROOT") or None,
            limit=limit,
            commit=True,
            dry_run=dry_run,
            report_path=_setting("REPORT_PATH") or None,
            partners_only=_flag("PARTNERS_ONLY") or bool(layer),
            layer=layer,
            database=database,
            after_stage=None if dry_run else after_stage,
        )
    except LayerRejected as rejected:
        env.cr.rollback()
        print(f"refusing to commit: the {rejected} validator did not pass; the stage was rolled back")
        return 1

    if dry_run:
        return 0
    if layer:
        print(f"layer {layer} validated and committed")
        return 0
    summary = result.get("summary") or {}
    if summary.get("final_status") == "failed":
        print("IMPORT FAILED: material errors — see summary errors list")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
