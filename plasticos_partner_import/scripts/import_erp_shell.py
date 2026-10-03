"""Odoo-shell driver for ``make import-erp``.

Executed inside ``odoo shell`` against the target database (Makefile pipes this
file into the shell). Configuration arrives via environment variables so the
single file serves both the docker and the no-Docker harness paths:

* ``ERP_DRY`` — ``1`` for a resolve-and-map preview (nothing persisted)
* ``ERP_LIMIT`` — process at most N transactions (diagnostics)
* ``ERP_PAYLOAD_ROOT`` — non-default payload directory
* ``ERP_REPORT_PATH`` — write the machine-readable summary JSON here

Exit code: nonzero when the summary reports ``failed``, so the Makefile target
fails closed on material import errors. Dry runs always exit 0.
"""

import os
import sys

from plasticos_partner_import.scripts.run_erp_import import run


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


def main() -> int:
    limit_raw = _setting("LIMIT").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else None

    result = run(
        _odoo_env(),
        payload_root=_setting("PAYLOAD_ROOT") or None,
        limit=limit,
        commit=True,
        dry_run=_flag("DRY"),
        report_path=_setting("REPORT_PATH") or None,
    )
    summary = result.get("summary") or {}
    if summary.get("final_status") == "failed":
        print("IMPORT FAILED: material errors — see summary errors list")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
