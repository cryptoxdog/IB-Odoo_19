"""Odoo-shell driver for ``make import-vanillasoft``.

Executed inside ``odoo shell`` against the target database (the Makefile pipes
this file into the shell). Configuration arrives via environment variables:

* ``VANILLASOFT_CALL_FLOOR`` — call history floor (ISO UTC). **Required.** A
  full import has no safe default floor: a 30-day fallback would run the
  rolling window under the full-import name and report it complete.
* ``VANILLASOFT_CONTACT_FLOOR`` — contact floor (ISO UTC); defaults to the call
  floor (full-import semantics).
* ``VANILLASOFT_REPORT_PATH`` — write the machine-readable summary JSON here
  (default ``.l9/pr/import-vanillasoft-summary.json``).

Preflight is fail-closed: a missing call floor, a missing VanillaSoft API key
or an unreachable endpoint exits nonzero BEFORE any write. Exit codes:
0 success/partial, 1 material failure, 2 preflight failure.

The printed summary names the run's kind and the bounds it asked the provider
for, beside the counters: ``partial`` with a scope note means the declared
scope completed with a named limitation (an unproven census, a clamped
watermark, orphaned calls), never an implied full history.
"""

import json
import os
import sys


def _env_flag(name: str) -> str:
    return os.environ.get(name, "").strip()


def _odoo_env():
    env = globals().get("env")
    if env is None:
        raise SystemExit("no Odoo environment (run inside `odoo shell`)")
    return env


def main() -> int:
    # The floor is checked before the Odoo environment is touched: the refusal
    # is about the operator's request, not the database, and it must hold in
    # the pure-python tier too.
    call_floor = _env_flag("VANILLASOFT_CALL_FLOOR")
    if not call_floor:
        print(
            "PRECHECK FAILED: VANILLASOFT_CALL_FLOOR is not set. A full import has no safe default floor — "
            "pass an explicit ISO-8601 UTC instant, e.g. VANILLASOFT_CALL_FLOOR=2019-01-01T00:00:00Z "
            "(VANILLASOFT_CONTACT_FLOOR defaults to it)."
        )
        print("Nothing was imported.")
        return 2
    env = _odoo_env()
    from plasticos_crm_sync.models.crm_connection import ICP_ROOT, ICP_VS_KEY_PARAM
    from plasticos_crm_sync.services.import_summary import build_run_summary, utc_now
    from plasticos_crm_sync.services.orchestrator import SyncOrchestrator

    icp = env["ir.config_parameter"].sudo()
    api_key = (icp.get_param(ICP_VS_KEY_PARAM) or "").strip()
    root = (icp.get_param(ICP_ROOT) or "").strip() or "https://vanillasoft.net"
    if not api_key:
        print("PRECHECK FAILED: VanillaSoft API key is not set (Settings → PlasticOS CRM Sync).")
        print("Nothing was imported.")
        return 2
    if not root.startswith("https://"):
        print(f"PRECHECK FAILED: VanillaSoft root endpoint is not HTTPS: {root!r}.")
        print("Nothing was imported.")
        return 2

    connection = env["plasticos.crm.connection"].get_or_create_vanillasoft_connection()

    contact_floor = _env_flag("VANILLASOFT_CONTACT_FLOOR") or None

    report_path = _env_flag("VANILLASOFT_REPORT_PATH") or ".l9/pr/import-vanillasoft-summary.json"

    start_time = utc_now()
    orch = SyncOrchestrator(env)
    orch.error_rows = []
    try:
        run = orch.run_full_import(
            connection,
            call_history_floor=call_floor,
            contact_modified_floor=contact_floor,
        )
    except Exception as exc:  # noqa: BLE001 - fail closed with the real reason
        print(f"IMPORT FAILED: {type(exc).__name__}: {str(exc).strip().splitlines()[0]}")
        return 1

    summary = build_run_summary(run, error_rows=orch.error_rows, start_time=start_time)
    parent = os.path.dirname(os.path.abspath(report_path))
    os.makedirs(parent, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("=== VANILLASOFT IMPORT SUMMARY ===")
    print(f"status      : {summary['final_status']}")
    print(f"kind        : {run.kind or 'unknown'}")
    print(f"contacts    : modified_after >= {run.contact_scope_from_utc or 'unknown'}")
    print(f"calls       : {run.call_scope_from_utc or 'unknown'} -> {run.call_scope_to_utc or 'not reached'}")
    if run.error_excerpt:
        print("scope note  :")
        for line in str(run.error_excerpt).splitlines()[:8]:
            print(f"  {line[:200]}")
    print(
        f"seen/valid  : {summary['records_seen']} / {summary['records_valid']} (rejected {summary['records_rejected']})"
    )
    print(
        "created/updated/unchanged: "
        f"{summary['records_created']} / {summary['records_updated']} / {summary['records_unchanged']}"
    )
    print(f"duplicates  : {summary['duplicates']}  orphans buffered: {run.orphans_buffered or 0}")
    if summary["errors"]:
        print(f"errors      : {len(summary['errors'])} (first 10 below)")
        for row in summary["errors"][:10]:
            print(f"  - {row['record_ref']}: {row['message'][:160]}")
    if summary["final_status"] == "failed":
        print("IMPORT FAILED: material errors — see summary errors list")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
