"""Project a CRM sync run onto the shared import-run summary contract.

Odoo-free module (dataclass/typing only) so the projection is exercised by the
pure-python tier; the shared contract is
``contracts/schemas/draft/import-run-summary.schema.json`` and
``scripts/validate_import_summary.py`` validates the emitted JSON.

Counter semantics (documented, honest accounting):

* ``records_seen`` — contacts + calls the adapter returned.
* ``records_rejected`` — rows that did not land in their target table during
  this run: identity-conflict (duplicate_rejected) contacts, failed rows, and
  deferred calls (buffered as orphans because their lead is not imported yet).
* ``records_created/updated/unchanged`` — classification counters from the run.
* ``duplicates`` — contact identity conflicts (duplicate_rejected).
* ``errors`` — per-record failures plus identity-conflict rows; never secrets.
  Deferred calls carry no error row: their durable trace is the orphan record.
  A required material mapping that failed after the contact landed is listed
  here and does not increment ``records_rejected``: the contact still counts
  as created, updated, or unchanged.
* ``final_status`` — ``failed`` on any failed row or a failed run status,
  ``partial`` on a census gap, identity conflicts, deferred calls, a row whose
  ``category`` is ``required_mapping``, or an informational notice, else
  ``success``. An optional contact fallback (non-US mobile, unresolved
  country or state) stays on the row and does not change this status.

Reconciliation: ``seen == created + updated + unchanged + rejected``. Every
seen call is represented exactly once: a call buffered as an orphan is
counted once, as deferred (inside ``records_rejected``), and never as a
successful write. ``orphans_buffered`` on the run is that per-run count; the
orphan record itself is kept for later resolution and ``orphans_resolved``
reports resolutions (which may include orphans from earlier runs and are
therefore outside this run's seen equation).
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = [
    "OPTIONAL_CONTEXT",
    "REQUIRED_MAPPING",
    "build_run_summary",
    "business_acceptance",
    "informational_notices",
    "required_mapping_errors",
    "utc_now",
]

SUMMARY_SOURCE = "vanillasoft"
REQUIRED_MAPPING = "required_mapping"
OPTIONAL_CONTEXT = "optional_context"


def is_informational_notice(row: dict) -> bool:
    """A notice explains scope. It is not a required mapping failure."""
    return row.get("informational") is True


def required_mapping_errors(error_rows: list[dict] | None) -> list[dict]:
    """Rows the producer marked as a required mapping that did not land.

    The category is explicit. A message alone is not a required mapping:
    optional contact fallbacks and identity conflicts are other categories.
    """
    rows = []
    for row in error_rows or []:
        if row.get("category") != REQUIRED_MAPPING:
            continue
        if not str(row.get("message") or "").strip():
            continue
        rows.append(row)
    return rows


def informational_notices(error_rows: list[dict] | None) -> list[dict]:
    return [row for row in error_rows or [] if str(row.get("message") or "").strip() and is_informational_notice(row)]


def business_acceptance(summary: dict) -> str:
    """FAIL unless the shared summary is a complete success.

    ``import_vanillasoft_shell`` may exit 0 on ``partial``. Business acceptance
    does not. A required mapping error is FAIL even if ``final_status`` was
    left at ``success``.
    """
    if summary.get("final_status") != "success":
        return "FAIL"
    if required_mapping_errors(summary.get("errors")):
        return "FAIL"
    return "PASS"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_run_summary(
    run,
    *,
    error_rows: list[dict[str, str]] | None = None,
    start_time: str | None = None,
    completion_time: str | None = None,
) -> dict:
    """Project a ``plasticos.crm.sync.run`` onto the shared summary shape."""
    error_rows = error_rows or []

    contacts_seen = run.contacts_seen or 0
    calls_seen = run.calls_seen or 0
    seen = contacts_seen + calls_seen

    # Calls buffered as orphans this run: seen, durably kept, not yet landed.
    deferred = getattr(run, "orphans_buffered", 0) or 0
    rejected = (run.contacts_duplicate_rejected or 0) + (run.contacts_failed or 0) + (run.calls_failed or 0) + deferred
    created = (run.contacts_created or 0) + (run.calls_created or 0)
    updated = (run.contacts_updated or 0) + (run.calls_updated or 0)
    unchanged = (run.contacts_unchanged or 0) + (run.calls_unchanged or 0)
    duplicates = run.contacts_duplicate_rejected or 0
    mapping_errors = required_mapping_errors(error_rows)
    notices = informational_notices(error_rows)

    if run.status == "failed" or (run.contacts_failed or run.calls_failed):
        final_status = "failed"
    elif run.status == "partial" or duplicates or deferred or mapping_errors or notices:
        final_status = "partial"
    else:
        final_status = "success"

    return {
        "source": SUMMARY_SOURCE,
        "start_time": start_time or utc_now(),
        "completion_time": completion_time or utc_now(),
        "records_seen": seen,
        "records_valid": max(seen - rejected, 0),
        "records_rejected": rejected,
        "records_created": created,
        "records_updated": updated,
        "records_unchanged": unchanged,
        "duplicates": duplicates,
        "errors": [dict(row) for row in error_rows],
        "final_status": final_status,
    }
