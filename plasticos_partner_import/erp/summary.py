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
  In the ``transactions`` bucket a rejected row is a worksheet that compiled no
  ``plasticos.transaction`` (no sale order link, a sale order that was not
  confirmed, or a compile that failed); its purchase documents and vendor
  bills may still have been realized on their own identity (the run census
  names it), but it is never counted as a created transaction. ``created``
  is counted only once the transaction exists. A worksheet whose customer is
  the inventory counterparty ``(INV)`` is not an external sale: a recognized
  inbound receipt is ``skipped`` because no ``plasticos.transaction`` is the
  correct document, and a held or cancelled inbound receipt is ``rejected``
  with its inventory census reason. Every unresolved entry is exactly one source row (the importer records a
  parent failure once per suppressed child row, never once per parent), so
  ``len(unresolved)`` is a row count and the reconciliation below holds.
* ``records_unchanged`` — identity-resolved rows that needed no write on replay
  (including set-semantics buckets: contact roles, transaction lines).
* ``records_created`` / ``records_updated`` — identity-resolved rows written.
* ``errors`` — bounded diagnostic detail for failed transactions and unresolved
  references, keyed by the source-native identifier. The complete rejected-row
  accounting remains ``records_rejected``. At most the shared contract's 1000
  diagnostic entries are emitted. A reconciliation failure and each run-level
  failure reserve slots among them. Never contains secrets.
* ``failures`` (on the report, not the summary) — mandatory run-level checks
  that did not pass, such as the payables identity reconciliation
  (``payables_reconciliation``). A failure is not a row: it enters no counter,
  relabels nothing, and is projected into ``errors`` under its check name so
  the run is ``failed`` while every counter stays what the run measured.
* ``final_status`` — ``success`` when nothing was rejected, ``partial`` when
  rows were rejected or left unresolved without a failed unit, ``failed`` when
  a logical unit (a ``BuySellNo``) raised and was rolled back, when a
  run-level check failed, or when the reconciliation below does not close. An
  unresolved source reference is a rejected row the source itself explains (an
  inactive counterparty's child, an unknown representative); it is not a
  failure of the run, so a partner import with known unresolved rows exits
  partial, not failed.

``seen == created + updated + unchanged + rejected`` closes the reconciliation:
an imported-with-anomaly row still lands in created/updated, and anomalies are
diagnostics on those rows, never a separate loss bucket. The equation is
enforced, not assumed: when it does not close, the counters are reported as
they are, a ``reconciliation`` error names the gap, and the run is ``failed``.
Rows the pipeline never accounted for (a deal table nothing realized, a failed
unit's lines) are evidence of a broken run, never relabelled as rejected.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

__all__ = ["data_verdict", "exceptions_digest", "import_run_summary", "run_exit_status", "utc_now"]

SUMMARY_SOURCE = "erp"
# ``source_counts`` key that tallies rows already counted in their own table.
SOURCE_COUNT_DIAGNOSTIC = "violations"
# ``record_ref`` of the run-level error a reconciliation gap emits.
RECONCILIATION_REF = "reconciliation"
# ``record_ref`` (and report ``check``) of the payables identity reconciliation.
PAYABLES_RECONCILIATION_REF = "payables_reconciliation"
# Producer bounds for the shared contract's ``errors.maxItems`` and
# ``errors.items.message.maxLength``. Not read from the schema at runtime.
ERROR_ROW_LIMIT = 1000
ERROR_MESSAGE_LIMIT = 2000


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
    failures = result.get("failures") or []

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
    # Run-level entries: never rows, never counted, always kept in ``errors``
    # ahead of the diagnostic cap so a failed run can be read from the summary.
    run_level = [
        {"record_ref": str(row.get("check") or "?"), "message": str(row.get("detail") or "?")[:ERROR_MESSAGE_LIMIT]}
        for row in failures
    ]
    if accounted != seen:
        run_level.append(
            {
                "record_ref": RECONCILIATION_REF,
                "message": (
                    f"records_seen {seen} != created {created} + updated {updated} + unchanged {unchanged} "
                    f"+ rejected {total_rejected} = {accounted}; {seen - accounted} source rows unaccounted"
                ),
            }
        )
    error_rows = [*error_rows[: max(ERROR_ROW_LIMIT - len(run_level), 0)], *run_level][:ERROR_ROW_LIMIT]

    if errors or failures or accounted != seen:
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


def run_exit_status(result: dict, *, dry_run: bool = False, layer: str | None = None) -> int:
    """Process exit status of an import run: nonzero whenever the run cannot be called successful.

    A run-level failure (``result["failures"]``) fails every mode, a dry run
    and a single-layer run included: a preview whose payables reconciliation
    does not close must not exit clean. An applied full run also fails when
    its summary reports ``failed``. A layer run that reached this point passed
    its validator, and a dry run emits no summary, so the summary is read only
    for an applied full run.
    """
    if result.get("failures"):
        return 1
    if dry_run or layer:
        return 0
    summary = result.get("summary") or {}
    return 1 if summary.get("final_status") == "failed" else 0


# Native documents are realized as draft account.move with no payment. No
# approved mapping from ERP posting/settlement status exists, so historical
# accounting state is never accepted by an import run.
ACCOUNTING_STATE = "draft_unposted"
ACCOUNTING_ACCEPTANCE = "BLOCKED_ARCHITECTURE"


def exceptions_digest(summary: dict) -> str:
    """Digest of what a run left open: status, rejected count and every reported error reference."""
    errors = sorted(
        (str(row.get("record_ref") or ""), str(row.get("message") or "")) for row in summary.get("errors") or []
    )
    body = {
        "final_status": summary.get("final_status"),
        "records_rejected": summary.get("records_rejected"),
        "errors": errors,
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def data_verdict(result: dict, *, partners_only: bool = False) -> dict:
    """Data acceptance of an applied run, separate from its process exit status.

    Exit 0 means the script completed: a ``partial`` run exits 0. The verdict
    says whether the data is complete: only a ``success`` summary with no
    run-level failure is. Open exceptions are the summary's rejected rows and
    error references; ``exceptions_digest`` lets an operator accept exactly
    that set and nothing else.
    """
    summary = result.get("summary") or {}
    failures = result.get("failures") or []
    status = summary.get("final_status") or "unknown"
    complete = status == "success" and not failures
    verdict = {
        "final_status": status,
        "data_complete": complete,
        "open_exceptions": int(summary.get("records_rejected") or 0) + len(failures),
        "run_failures": [str(row.get("check") or "?") for row in failures],
        "exceptions_digest": exceptions_digest(summary),
    }
    if not partners_only:
        verdict["accounting_state"] = ACCOUNTING_STATE
        verdict["accounting_acceptance"] = ACCOUNTING_ACCEPTANCE
    return verdict
