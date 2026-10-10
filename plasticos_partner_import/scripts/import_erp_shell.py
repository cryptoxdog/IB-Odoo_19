"""Odoo-shell driver for ``make import-erp``.

Executed inside ``odoo shell`` against the target database (Makefile pipes this
file into the shell). Configuration arrives via environment variables so the
single file serves both the docker and the no-Docker harness paths:

* ``ERP_DRY`` — ``1`` for a resolve-and-map preview (nothing persisted)
* ``ERP_LIMIT`` — newest N worksheets, or ``25%`` for the newest quarter (diagnostics / test databases)
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
  not opened. Without this flag, a full run writes sale orders, purchase
  orders, and invoices from the direct SQL source.
* ``ERP_LAYER`` — ``counterparties``, ``addresses``, ``contacts``, ``roles``,
  or ``salesreps``. Only that table is read, and only after the previous
  layer's validator passes.
* ``ERP_REQUIRE_EMPTY`` — ``0`` allows a database that already has business
  partners. Any other value (including unset) refuses a full import or the
  ``counterparties`` layer when any ``res.partner`` row is not the company, a
  login user, or a localization-owned (``l10n_*``) reference partner.

Order of operations for an applied run: database check → (layer mode) the
previous layer's check → import each stage → that stage's validator → commit.
A validator that fails raises before the commit, the transaction is rolled
back, and nothing of the run is persisted. A full dry run still checks that
sale, purchase, and account are installed. It does not apply the write-target
database check. Partner-only and single-layer dry runs do not persist. Exit
code is otherwise nonzero when a validator fails, when a mandatory run-level
check (the payables identity reconciliation) fails in any mode, or when the
summary reports ``failed``, so the Makefile target fails closed
(``erp.summary.run_exit_status``).
"""

import os
import sys

from odoo.addons.plasticos_partner_import.erp import reader
from odoo.addons.plasticos_partner_import.erp import summary as import_summary
from odoo.addons.plasticos_partner_import.erp.limits import parse_limit
from odoo.addons.plasticos_partner_import.scripts.run_erp_import import run
from odoo.addons.plasticos_partner_import.scripts.validate_partner_layer import (
    DATABASE_CHECK,
    LAYER_BEFORE,
    LayerRejected,
    check_full_run_extension,
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

    A pristine initialized Odoo database may contain the company partner,
    login-user partners, and localization-owned res.partner reference records.
    Those are infrastructure/reference data, not imported business partners.
    Any other pre-existing partner blocks a first historical import.
    """
    if _setting("REQUIRE_EMPTY").strip().lower() in {"0", "false", "no", "n"}:
        return
    # Direct SQL justification: a whole-table census before a bulk load; the ORM would browse every partner.
    env.cr.execute(
        """
        SELECT count(*)
          FROM res_partner AS partner
         WHERE partner.id NOT IN (
                SELECT partner_id
                  FROM res_users
                 WHERE partner_id IS NOT NULL

                UNION

                SELECT partner_id
                  FROM res_company
                 WHERE partner_id IS NOT NULL
               )
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS data
                 WHERE data.model = 'res.partner'
                   AND data.res_id = partner.id
                   AND LEFT(data.module, 5) = 'l10n_'
               )
        """
    )
    extra = int(env.cr.fetchone()[0])
    # Direct SQL justification: same bulk census, total rows including archived partners.
    env.cr.execute("SELECT count(*) FROM res_partner")
    total = int(env.cr.fetchone()[0])
    print(f"res.partner before import: {total} (pre-existing business partners: {extra})")
    if extra:
        raise SystemExit("refusing import: database already contains business partner rows")


def main() -> int:
    try:
        limit = parse_limit(_setting("LIMIT"))
    except ValueError as invalid:
        raise SystemExit(f"refusing import: {invalid}") from None
    env = _odoo_env()
    dry_run = _flag("DRY")
    layer = _setting("LAYER").strip().lower() or None
    if layer and layer not in LAYER_BEFORE:
        raise SystemExit(f"ERP_LAYER must be one of {', '.join(LAYER_BEFORE)}")
    if dry_run and not _flag("PARTNERS_ONLY") and not layer:
        failures: list[str] = []
        check_full_run_extension(env, failures)
        if failures:
            for message in failures:
                print(message)
            return 1
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

    for failure in result.get("failures") or []:
        print(f"IMPORT FAILED: {failure.get('check')}: {failure.get('detail')}")
    status = import_summary.run_exit_status(result, dry_run=dry_run, layer=layer)
    if status:
        if not result.get("failures"):
            print("IMPORT FAILED: material errors — see summary errors list")
        return status
    if layer:
        print(f"layer {layer} validated and committed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
