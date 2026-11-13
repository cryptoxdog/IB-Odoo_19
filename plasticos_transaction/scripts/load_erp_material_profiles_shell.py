"""Odoo-shell driver for ``make import-erp-material-profiles``.

Executed inside ``odoo shell`` against the target database (the Makefile pipes
this file into the shell). Configuration arrives through the environment:

* ``ERP_PROFILE_SUPPLIERS`` / ``ERP_PROFILE_CUSTOMERS`` — the two operator
  files (Product, Supplier or Customer, Ship From or Ship To). Both are
  required and both are read as one list.
* ``ERP_PROFILE_DRY`` — ``1`` resolves and counts, then rolls back.
* ``ERP_PROFILE_REPORT_PATH`` — write the machine-readable summary here.
* ``ERP_TARGET_DB`` — the database an applied run may write. The ERP import's
  database check (``validate_partner_layer.check_database``) refuses any other
  database and any production database. This driver has no production permit.

The summary follows ``contracts/schemas/draft/import-run-summary.schema.json``:
``records_seen == created + updated + unchanged + rejected``. The exit code is
nonzero when the database check fails, when a file is missing or malformed, or
when the summary reports ``failed``. A run with rejected rows is ``partial``
and exits 0; every rejected row is listed with its reason.
"""

import json
import os
import sys
from pathlib import Path

from odoo.addons.plasticos_partner_import.scripts.validate_partner_layer import check_database

LOADER = "plasticos.erp.material.profile.loader"


def _setting(name: str) -> str:
    return (os.environ.get(f"ERP_PROFILE_{name}") or "").strip()


def _odoo_env():
    """The Odoo environment injected by ``odoo shell`` stdin execution."""
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return env


def main() -> int:
    env = _odoo_env()
    dry_run = _setting("DRY").lower() in {"1", "true", "yes", "y"}
    paths = []
    for name in ("SUPPLIERS", "CUSTOMERS"):
        path = _setting(name)
        if not path or not Path(path).is_file():
            print(f"refusing load: ERP_PROFILE_{name} does not name a readable file")
            return 2
        paths.append(path)
    if LOADER not in env:
        print("refusing load: plasticos_transaction is not installed or not upgraded on this database")
        return 2
    if not dry_run:
        failures: list[str] = []
        check_database(env, failures)
        if failures:
            for failure in failures:
                print(f"refusing load: {failure}")
            return 2

    try:
        report = env[LOADER].load(paths, dry_run=dry_run)
    except ValueError as malformed:
        env.cr.rollback()
        print(f"refusing load: {malformed}")
        return 2
    summary = report["summary"]
    if dry_run or summary["final_status"] == "failed":
        env.cr.rollback()
    else:
        env.cr.commit()

    report_path = _setting("REPORT_PATH")
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("ERP material profiles" + (" [DRY RUN, rolled back]" if dry_run else ""))
    for field in ("records_seen", "records_created", "records_updated", "records_unchanged", "records_rejected"):
        print(f"  {field}: {summary[field]}")
    for reason, count in report["rejected_by_reason"].items():
        print(f"  rejected, {reason}: {count}")
    for anomaly in report["anomalies"]:
        print(f"  anomaly {anomaly['key']}: {anomaly['detail']}")
    print(f"  final_status: {summary['final_status']}")
    return 1 if summary["final_status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
