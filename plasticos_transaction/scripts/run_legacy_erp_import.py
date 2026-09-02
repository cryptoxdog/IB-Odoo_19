#!/usr/bin/env python3
"""Non-interactive entrypoint for the LegacyErp historical import.

One deterministic entrypoint, no UI, no wizard, no cron. Run it from an Odoo
shell against the target database::

    from plasticos_transaction.scripts.run_legacy_erp_import import run
    run(env)                                   # full import
    run(env, dry_run=True)                     # resolve + map, persist nothing
    run(env, limit=50)                         # first 50 transactions only
    run(env, commit=True)                      # commit between transactions
    run(env, payload_root="/path/to/export")   # non-default payload location

``commit=True`` commits only *between* complete transactions — never inside
one. A failed ``BuySellNo`` is rolled back to its savepoint, leaving no partial
transaction and no stale identity marker, so a re-run reprocesses it.

The import is idempotent: running it twice creates no duplicate counterparty,
location, contact, contact-role, transaction, or transaction line, because every
record is addressed by its stable LegacyErp source key.
"""

import json


def run(
    env,
    payload_root: str | None = None,
    limit: int | None = None,
    commit: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    """Execute the LegacyErp import and print an accounting report.

    Args:
        env: Odoo environment.
        payload_root: Override the tracked payload directory.
        limit: Process at most this many transactions (diagnostics only).
        commit: Commit between complete transactions.
        dry_run: Resolve and map everything without persisting.
        verbose: Print the human-readable summary.

    Returns:
        The import report produced by ``plasticos.legacy_erp.import``.
    """
    result = env["plasticos.legacy_erp.import"].run(
        payload_root=payload_root,
        limit=limit,
        commit=commit,
        dry_run=dry_run,
    )

    if verbose:
        _print_report(result, dry_run=dry_run)
    return result


def _print_report(result: dict, dry_run: bool) -> None:
    print(f"\n=== LEGACY_ERP IMPORT ({'DRY RUN' if dry_run else 'APPLIED'}) ===")
    print(f"payload kind : {result['payload_kind']}")
    print(f"source counts: {json.dumps(result['source_counts'], sort_keys=True)}")

    print("\n--- results ---")
    header = f"{'entity':<20} {'created':>8} {'updated':>8} {'skipped':>8}"
    print(header)
    print("-" * len(header))
    for entity, counts in result["counts"].items():
        print(f"{entity:<20} {counts['created']:>8} {counts['updated']:>8} {counts['skipped']:>8}")

    print(f"\nunresolved references : {len(result['unresolved'])}")
    print(f"mapping anomalies     : {len(result['anomalies'])}")
    print(f"failed transactions   : {len(result['errors'])}")

    for label, rows in (("unresolved", result["unresolved"]), ("anomalies", result["anomalies"])):
        if rows:
            print(f"\nfirst 10 {label}:")
            for row in rows[:10]:
                print(f"  - {json.dumps(row, sort_keys=True)}")

    if result["errors"]:
        print("\nfirst 10 failed transactions:")
        for row in result["errors"][:10]:
            print(f"  - {row['buysell_no']}: {row['error']}")
