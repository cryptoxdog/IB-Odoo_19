"""Odoo-shell driver for ``make import-erp``.

Executed inside ``odoo shell`` against the target database (Makefile pipes this
file into the shell). Configuration arrives via environment variables so the
single file serves both the docker and the no-Docker harness paths:

* ``ERP_DRY`` — ``1`` for a resolve-and-map preview (nothing persisted)
* ``ERP_LIMIT`` — process at most N transactions (diagnostics)
* ``ERP_PAYLOAD_ROOT`` — non-default payload directory
* ``ERP_REPORT_PATH`` — write the machine-readable summary JSON here
* ``ERP_PARTNERS_ONLY`` — ``1`` imports only CounterParty, Address, Contact,
  and ContactRoleAssignment. Deal files are not opened.
* ``ERP_LAYER`` — ``counterparties``, ``addresses``, ``contacts``, or ``roles``.
  Only that file is opened, and only after the previous layer's validator
  passes (``database`` before ``counterparties``). Unresolved placeholder rows
  do not fail the process; the layer's own validator is the exit code.
* ``ERP_REQUIRE_EMPTY`` — ``0`` allows a database that already has business
  partners. Any other value (including unset) refuses a full import or the
  ``counterparties`` layer unless the only ``res.partner`` rows are the company
  and the login users. Later layers are gated by the previous validator.

Exit code: nonzero when the summary reports ``failed`` or a layer validator
fails, so the Makefile target fails closed. Dry runs always exit 0.
"""

import os
import sys

from odoo.addons.plasticos_partner_import.scripts.run_erp_import import run
from odoo.addons.plasticos_partner_import.scripts.validate_partner_layer import LAYER_BEFORE, validate


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
    if not dry_run and layer in (None, "counterparties"):
        _require_empty_partner_set(env)
    if layer and not dry_run and validate(env, LAYER_BEFORE[layer]):
        print(f"refusing layer {layer}: the {LAYER_BEFORE[layer]} validator did not pass")
        return 1

    result = run(
        env,
        payload_root=_setting("PAYLOAD_ROOT") or None,
        limit=limit,
        commit=True,
        dry_run=dry_run,
        report_path=_setting("REPORT_PATH") or None,
        partners_only=_flag("PARTNERS_ONLY") or bool(layer),
        layer=layer,
    )
    summary = result.get("summary") or {}
    if layer:
        if dry_run:
            return 0
        print(f"layer {layer} committed")
        return validate(env, layer)
    if summary.get("final_status") == "failed":
        print("IMPORT FAILED: material errors — see summary errors list")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
