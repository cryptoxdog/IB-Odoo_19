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

import re
from datetime import UTC, datetime

__all__ = [
    "OPTIONAL_CONTEXT",
    "REQUIRED_MAPPING",
    "build_run_summary",
    "business_acceptance",
    "informational_notices",
    "required_mapping_errors",
    "review_rows",
    "utc_now",
]

SUMMARY_SOURCE = "vanillasoft"
REQUIRED_MAPPING = "required_mapping"
OPTIONAL_CONTEXT = "optional_context"
ERROR_ROW_LIMIT = 1000
# ADR-132: rows the operator reviews after every run. They are optional_context
# (the run does not fail) and are kept ahead of other rows under the cap.
MATERIAL_PLACEMENT_REVIEW = "MATERIAL_PLACEMENT_REVIEW"
MATERIAL_FIELD_IGNORED = "MATERIAL_FIELD_IGNORED"
REVIEW_ERROR_TYPES = (MATERIAL_PLACEMENT_REVIEW, MATERIAL_FIELD_IGNORED)
ERROR_MESSAGE_LIMIT = 2000
ERROR_TYPE_LIMIT = 200
_ERROR_CATEGORIES = frozenset({REQUIRED_MAPPING, OPTIONAL_CONTEXT})
# Quoted values, then an unquoted token that stops at whitespace and the usual
# assignment delimiters. The key and the value are both removed.
_QUOTED_VALUE = r'"[^"]*"|\'[^\']*\''
_BARE_VALUE = r"[^\s,;&)\]}>]+"
_ASSIGNED_VALUE = rf"(?:{_QUOTED_VALUE}|{_BARE_VALUE})"
_KEY_PATTERN = r"api[ _-]?key|apikey|password|token|bearer"
_SECRET_ASSIGNMENT = re.compile(rf"(?i)(?<![A-Za-z0-9])[\"']?(?:{_KEY_PATTERN})[\"']?\s*[:=]\s*{_ASSIGNED_VALUE}")
_AUTH_HEADER = re.compile(
    rf"(?i)(?<![A-Za-z0-9])authorization\s*[:=]\s*"
    rf"(?:(?:bearer|basic)\s+)?"
    rf"(?:(?:api[ _-]?key|apikey)\s*[:=]\s*)?"
    rf"{_ASSIGNED_VALUE}"
)


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


def _redact_secret_values(text: str) -> str:
    """Remove secret-bearing assignments and auth headers, not diagnostic words."""
    previous = None
    while previous != text:
        previous = text
        text = _AUTH_HEADER.sub("[redacted]", text)
        text = _SECRET_ASSIGNMENT.sub("[redacted]", text)
    return text


def _public_message(message: object) -> str:
    """Drop credential values, then cap the public error string.

    Marker-only substitution left ``[redacted]=<secret>``. The whole assigned
    value is removed first. Truncation happens after that, so a value past the
    cap cannot survive as a fragment and a short status code in front of a
    secret is not cut away before the secret is recognized.
    """
    text = _redact_secret_values(str(message or ""))
    if len(text) > ERROR_MESSAGE_LIMIT:
        text = text[: ERROR_MESSAGE_LIMIT - 3] + "..."
    return text


def project_error_row(row: dict) -> dict:
    """Keep the typed fields the schema and business acceptance both read."""
    projected = {
        "record_ref": str(row.get("record_ref") or ""),
        "message": _public_message(row.get("message")),
    }
    category = row.get("category")
    if category in _ERROR_CATEGORIES:
        projected["category"] = category
    error_type = row.get("error_type")
    if isinstance(error_type, str) and error_type.strip():
        projected["error_type"] = error_type[:ERROR_TYPE_LIMIT]
    if row.get("informational") is True:
        projected["informational"] = True
    return projected


def project_error_rows(error_rows: list[dict] | None) -> list[dict]:
    """Project internal rows onto the strict summary. Required mappings survive a cap."""
    projected = [
        project_error_row(row)
        for row in error_rows or []
        if str(row.get("message") or "").strip() or str(row.get("record_ref") or "").strip()
    ]
    if len(projected) <= ERROR_ROW_LIMIT:
        return projected
    required = [row for row in projected if row.get("category") == REQUIRED_MAPPING]
    review = [
        row
        for row in projected
        if row.get("category") != REQUIRED_MAPPING and row.get("error_type") in REVIEW_ERROR_TYPES
    ]
    others = [
        row
        for row in projected
        if row.get("category") != REQUIRED_MAPPING and row.get("error_type") not in REVIEW_ERROR_TYPES
    ]
    return (required + review + others)[:ERROR_ROW_LIMIT]


def review_rows(summary: dict, error_type: str) -> list[dict]:
    """The summary's review rows of one kind (``MATERIAL_PLACEMENT_REVIEW`` / ``MATERIAL_FIELD_IGNORED``)."""
    return [row for row in summary.get("errors") or [] if row.get("error_type") == error_type]


def review_report_lines(summary: dict) -> list[str]:
    """The always-present NEEDS REVIEW sections the shell prints after the summary, untruncated."""
    placement = review_rows(summary, MATERIAL_PLACEMENT_REVIEW)
    ignored = review_rows(summary, MATERIAL_FIELD_IGNORED)
    lines = [
        f"=== NEEDS REVIEW: {len(placement)} VanillaSoft records have materials that were NOT placed "
        "(person oversees several sites) ==="
    ]
    lines.extend(f"  - {row['record_ref']}: {row['message']}" for row in placement)
    lines.append(f"=== NEEDS REVIEW: {len(ignored)} Material Type/Form fields ignored (several values) ===")
    lines.extend(f"  - {row['record_ref']}: {row['message']}" for row in ignored)
    return lines


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
        "errors": project_error_rows(error_rows),
        "final_status": final_status,
    }
