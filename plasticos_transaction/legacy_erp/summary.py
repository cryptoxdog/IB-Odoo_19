"""Map a LegacyErp import report onto the shared import-run summary contract.

Odoo-free: exercised by the pure-Python CI tier alongside the source layer.
The shared contract is ``contracts/schemas/draft/import-run-summary.schema.json``;
``scripts/validate_import_summary.py`` validates the emitted JSON.

Counter semantics (documented, honest accounting):

* ``records_seen`` — every source row the payload carried.
* ``records_rejected`` — rows refused (blank required values) plus unresolved
  source references and failed transactions: nothing that did not reach the DB.
  Every unresolved entry is exactly one source row (the importer records a
  parent failure once per suppressed child row, never once per parent), so
  ``len(unresolved)`` is a row count and the reconciliation below holds.
* ``records_unchanged`` — identity-resolved rows that needed no write on replay
  (including set-semantics buckets: contact roles, transaction lines).
* ``records_created`` / ``records_updated`` — identity-resolved rows written.
* ``errors`` — failed transactions and unresolved references, keyed by the
  source-native identifier. Never contains secrets.
* ``final_status`` — ``success`` when nothing failed, ``partial`` when some
  rows were rejected without a transaction failure, ``failed`` otherwise.

``seen == created + updated + unchanged + rejected`` closes the reconciliation:
an imported-with-anomaly row still lands in created/updated, and anomalies are
diagnostics on those rows, never a separate loss bucket.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["import_run_summary", "utc_now"]

SUMMARY_SOURCE = "legacy_erp"


def utc_now() -> str:
    """Current UTC timestamp in the shared summary format."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def import_run_summary(
    result: dict,
    *,
    start_time: str | None = None,
    completion_time: str | None = None,
) -> dict:
    """Project a ``plasticos.legacy_erp.import`` report onto the shared contract."""
    counts = result.get("counts") or {}
    source_counts = result.get("source_counts") or {}
    unresolved = result.get("unresolved") or []
    errors = result.get("errors") or []

    created = sum(bucket.get("created", 0) for bucket in counts.values())
    updated = sum(bucket.get("updated", 0) for bucket in counts.values())
    unchanged = sum(bucket.get("skipped", 0) for bucket in counts.values())
    rejected = sum(bucket.get("rejected", 0) for bucket in counts.values())
    seen = sum(source_counts.values())
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

    if error_rows:
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
