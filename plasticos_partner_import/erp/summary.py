"""Map an ERP import report onto the shared import-run summary contract.

Odoo-free: exercised by the pure-Python CI tier alongside the source layer.
The shared contract is ``contracts/schemas/draft/import-run-summary.schema.json``;
``scripts/validate_import_summary.py`` validates the emitted JSON.

Counter semantics (documented, honest accounting):

* ``records_seen`` — every source row the payload carried: the per-table
  figures of ``source_counts`` (the ``violations`` tally is a diagnostic view
  of rows already counted in their table and is not added again).
* ``records_rejected`` — rows refused (blank required values) plus unresolved
  source references and failed transactions: nothing that did not reach the DB.
  Every unresolved entry is exactly one source row (the importer records a
  parent failure once per suppressed child row, never once per parent), so
  ``len(unresolved)`` is a row count and the reconciliation below holds.
* ``records_unchanged`` — identity-resolved rows that needed no write on replay
  (including set-semantics buckets: contact roles, transaction lines).
* ``records_created`` / ``records_updated`` — identity-resolved rows written.
* ``errors`` — bounded diagnostic detail for failed transactions and unresolved
  references, keyed by the source-native identifier. The complete rejected-row
  accounting remains ``records_rejected``. At most the shared contract's 1000
  diagnostic entries are emitted. A reconciliation failure reserves one of
  those slots. Never contains secrets.
* ``final_status`` — ``success`` when nothing was rejected, ``partial`` when
  rows were rejected or left unresolved without a failed unit, ``failed`` when
  a logical unit (a ``BuySellNo``) raised and was rolled back or when the
  reconciliation below does not close. An unresolved
  source reference is a rejected row the source itself explains (an inactive
  counterparty's child, an unknown representative); it is not a failure of the
  run, so a partner import with known unresolved rows exits partial, not failed.

``seen == created + updated + unchanged + rejected`` closes the reconciliation:
an imported-with-anomaly row still lands in created/updated, and anomalies are
diagnostics on those rows, never a separate loss bucket. The equation is
enforced, not assumed: when it does not close, the counters are reported as
they are, a ``reconciliation`` error names the gap, and the run is ``failed``.
Rows the pipeline never accounted for (a deal table nothing realized, a failed
unit's lines) are evidence of a broken run, never relabelled as rejected.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["import_run_summary", "utc_now"]

SUMMARY_SOURCE = "erp"
# ``source_counts`` key that tallies rows already counted in their own table.
SOURCE_COUNT_DIAGNOSTIC = "violations"
# ``record_ref`` of the run-level error a reconciliation gap emits.
RECONCILIATION_REF = "reconciliation"
# Producer bound for the shared contract's ``errors.maxItems``. Not read from the schema at runtime.
ERROR_ROW_LIMIT = 1000


def utc_now() -> str:
    """Current UTC timestamp in the shared summary format."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def import_run_summary(
    result: dict,
    *,
    start_time: str | None = None,
    completion_time: str | None = None,
) -> dict:
    """Project a ``plasticos.erp.import`` report onto the shared contract."""
    counts = result.get("counts") or {}
    source_counts = result.get("source_counts") or {}
    unresolved = result.get("unresolved") or []
    errors = result.get("errors") or []

    created = sum(bucket.get("created", 0) for bucket in counts.values())
    updated = sum(bucket.get("updated", 0) for bucket in counts.values())
    unchanged = sum(bucket.get("skipped", 0) for bucket in counts.values())
    rejected = sum(bucket.get("rejected", 0) for bucket in counts.values())
    seen = sum(count for name, count in source_counts.items() if name != SOURCE_COUNT_DIAGNOSTIC)
    total_rejected = rejected + len(unresolved) + len(errors)

    error_rows = [
        {"record_ref": str(row.get("buysell_no") or "?"), "message": str(row.get("error") or "?")} for row in errors
    ]
    error_rows.extend(
        {
            "record_ref": str(row.get("key") or "?"),
            "message": f"{row.get('table')} {row.get('kind')}: {row.get('detail')}",
        }
        for row in unresolved
    )

    accounted = created + updated + unchanged + total_rejected
    reconciliation_error = None
    if accounted != seen:
        reconciliation_error = {
            "record_ref": RECONCILIATION_REF,
            "message": (
                f"records_seen {seen} != created {created} + updated {updated} + unchanged {unchanged} "
                f"+ rejected {total_rejected} = {accounted}; {seen - accounted} source rows unaccounted"
            ),
        }
    if reconciliation_error is None:
        error_rows = error_rows[:ERROR_ROW_LIMIT]
    else:
        error_rows = [*error_rows[: ERROR_ROW_LIMIT - 1], reconciliation_error]

    if errors or accounted != seen:
        final_status = "failed"
    elif total_rejected:
        final_status = "partial"
    else:
        final_status = "success"

    return {
        "source": SUMMARY_SOURCE,
        "start_time": start_time or utc_now(),
        "completion_time": completion_time or utc_now(),
        "records_seen": seen,
        "records_valid": max(seen - total_rejected, 0),
        "records_rejected": total_rejected,
        "records_created": created,
        "records_updated": updated,
        "records_unchanged": unchanged,
        "duplicates": 0,
        "errors": error_rows,
        "final_status": final_status,
    }
