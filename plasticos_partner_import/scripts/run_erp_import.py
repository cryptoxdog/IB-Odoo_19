#!/usr/bin/env python3
"""Non-interactive entrypoint for the ERP historical import.

One deterministic entrypoint, no UI, no wizard, no cron. Run it from an Odoo
shell against the target database::

    from plasticos_partner_import.scripts.run_erp_import import run
    run(env)                                   # full import
    run(env, dry_run=True)                     # resolve + map, persist nothing
    run(env, limit=50)                         # first 50 transactions only
    run(env, commit=True)                      # commit between transactions
    run(env, payload_root="/path/to/export")   # non-default payload location
    run(env, database=source, partners_only=True)  # direct read of the ERP database

``commit=True`` commits only *between* complete transactions — never inside
one. A failed ``BuySellNo`` is rolled back to its savepoint, leaving no partial
transaction and no stale identity marker, so a re-run reprocesses it.
A partner-only run commits once, after every partner stage has passed its
``after_stage`` hook.

The import is idempotent: running it twice creates no duplicate counterparty,
location, contact, contact-role, transaction, or transaction line, because every
record is addressed by its stable ERP source key.
"""

import json
import os

from ..erp import summary as import_summary


def run(
    env,
    payload_root: str | None = None,
    limit: int | float | None = None,
    commit: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
    report_path: str | None = None,
    partners_only: bool = False,
    layer: str | None = None,
    database=None,
    after_stage=None,
    on_payload=None,
) -> dict:
    """Execute the ERP import, print an accounting report, and emit the
    shared import-run summary (``contracts/schemas/draft/import-run-summary``).

    Args:
        env: Odoo environment.
        payload_root: Override the tracked payload directory.
        limit: Newest N worksheets, or a fraction (0.25 = newest quarter); diagnostics and test databases.
        commit: Commit between complete transactions.
        dry_run: Resolve and map everything without persisting.
        verbose: Print the human-readable summary.
        report_path: When set, write the machine-readable summary JSON here.
        partners_only: Import only the partner tables. Do not open deal files.
        layer: Import one partner table. ``counterparties``, ``addresses``,
            ``contacts``, ``roles``, or ``salesreps``.
        database: A ``reader.DatabaseSource`` for a direct read of the ERP
            database. It takes precedence over ``payload_root``.
        after_stage: ``callable(layer_name, payload)`` run after each partner
            stage, before anything commits. Raising aborts the run.
        on_payload: ``callable(payload)`` run once the source is loaded and
            before any stage writes. Raising aborts the run.

    Returns:
        The import report produced by ``plasticos.erp.import`` with a
        ``summary`` key carrying the shared import-run summary (applied runs
        only; dry runs emit no summary).
    """
    start_time = import_summary.utc_now()
    result = env["plasticos.erp.import"].run(
        payload_root=payload_root,
        limit=limit,
        commit=commit,
        dry_run=dry_run,
        partners_only=partners_only,
        layer=layer,
        database=database,
        after_stage=after_stage,
        on_payload=on_payload,
    )

    if not dry_run:
        summary = import_summary.import_run_summary(
            result,
            start_time=start_time,
        )
        result["summary"] = summary
        if report_path:
            parent = os.path.dirname(os.path.abspath(report_path))
            os.makedirs(parent, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2, sort_keys=True)
                handle.write("\n")
            _write_census(census_path(report_path), result)
        if verbose:
            _print_summary(summary)
            _print_census(result.get("census") or {})
    elif verbose:
        _print_report(result, dry_run=True)
    return result


def census_path(report_path: str) -> str:
    """Sibling of the summary: ``<report>-census.json``.

    The shared summary contract allows no extra keys, so the source-exception
    census (every anomaly, and the grouped order-link, price-precision, and
    payables census with dollar exposure) is written beside it.
    """
    root, _ext = os.path.splitext(report_path)
    return f"{root}-census.json"


def _write_census(path: str, result: dict) -> None:
    payload = {
        "census": result.get("census") or {},
        "anomalies": result.get("anomalies") or [],
        "unresolved": result.get("unresolved") or [],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _print_census(census: dict) -> None:
    if not census:
        return
    print("\n=== SOURCE EXCEPTION CENSUS ===")
    for group in census.get("lines_by_reason") or []:
        print(
            f"{group['side']:<9} {group['reason']:<28} lines {group['lines']:>6}  worksheets {group['worksheets']:>5}"
            f"  keys {group['distinct_keys']:>5}  sale {group['sale_amount']:>14,.2f}"
            f"  purchase {group['purchase_amount']:>14,.2f}"
        )
    for name, view in (census.get("worksheets") or {}).items():
        print(
            f"{name}: {view['worksheets']} worksheets, {view['lines']} lines, sale {view['sale_amount']:,.2f},"
            f" purchase {view['purchase_amount']:,.2f}, partner active {view['partner_active']},"
            f" inactive/absent {view['partner_inactive_or_absent']}"
        )
    drift = census.get("price_precision") or {}
    if drift:
        print(
            f"price precision ({drift.get('digits')} decimals): {drift.get('lines')} lines drift,"
            f" net {drift.get('net_drift', 0):,.2f}, abs {drift.get('abs_drift', 0):,.2f},"
            f" max {drift.get('max_abs_drift', 0):,.2f}"
        )
    for bucket, tally in (census.get("payables") or {}).items():
        print(
            f"payables {bucket:<34} rows {tally['rows']:>6}  worksheets {tally['worksheets']:>5}  {tally['amount']:>14,.2f}"
        )
    reconciliation = census.get("payables_reconciliation") or {}
    if reconciliation:
        from ..erp.native_orders import reconciliation_gap  # noqa: PLC0415

        verdict = "CLOSES" if reconciliation["closes"] else f"OPEN: {reconciliation_gap(reconciliation)}"
        print(
            f"payables reconciliation: source {reconciliation.get('source_rows')} = billed"
            f" {reconciliation['billed_rows']} + quarantined {reconciliation['quarantined_rows']}"
            f" + excluded {reconciliation.get('excluded_rows', 0)} -> {verdict}"
        )


def _print_summary(summary: dict) -> None:
    print("\n=== ERP IMPORT SUMMARY ===")
    print(f"status      : {summary['final_status']}")
    print(
        f"seen/valid  : {summary['records_seen']} / {summary['records_valid']} (rejected {summary['records_rejected']})"
    )
    print(
        "created     : {records_created}  updated: {records_updated}  "
        "unchanged: {records_unchanged}  duplicates: {duplicates}".format(**summary)
    )
    if summary["errors"]:
        print(f"errors      : {len(summary['errors'])} (first 10 below)")
        for row in summary["errors"][:10]:
            print(f"  - {row['record_ref']}: {row['message'][:160]}")


def _print_report(result: dict, dry_run: bool) -> None:
    print(f"\n=== ERP IMPORT ({'DRY RUN' if dry_run else 'APPLIED'}) ===")
    print(f"payload kind : {result['payload_kind']}")
    if result.get("source_origin"):
        print(f"source       : {result['source_origin']}")
    print(f"source counts: {json.dumps(result['source_counts'], sort_keys=True)}")

    print("\n--- results ---")
    header = f"{'entity':<20} {'created':>8} {'updated':>8} {'skipped':>8} {'rejected':>8}"
    print(header)
    print("-" * len(header))
    for entity, counts in result["counts"].items():
        print(
            f"{entity:<20} {counts['created']:>8} {counts['updated']:>8} {counts['skipped']:>8} {counts['rejected']:>8}"
        )

    print(f"\nunresolved references : {len(result['unresolved'])}")
    print(f"mapping anomalies     : {len(result['anomalies'])}")
    print(f"failed transactions   : {len(result['errors'])}")
    for failure in result.get("failures") or []:
        print(f"RUN FAILED            : {failure['check']}: {failure['detail']}")

    for label, rows in (("unresolved", result["unresolved"]), ("anomalies", result["anomalies"])):
        if rows:
            print(f"\nfirst 10 {label}:")
            for row in rows[:10]:
                print(f"  - {json.dumps(row, sort_keys=True)}")

    if result["errors"]:
        print("\nfirst 10 failed transactions:")
        for row in result["errors"][:10]:
            print(f"  - {row['buysell_no']}: {row['error']}")
