"""CRM sync orchestrator — DTO → ORM write path with watermarks and orphans."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ..adapters.base import CanonicalCall, CanonicalLead, CrmAdapterError
from ..adapters.registry import get_adapter
from .approved_identity import (
    ACTIVE_COMPANY_CP_BY_VS,
    XMLID_MODULE,
    CrosswalkError,
    comment_with_note,
    load_crosswalk_map,
    phone_match_key,
    without_duplicate_contacts,
    xmlid_name,
)

_logger = logging.getLogger(__name__)

CRM_LEAD = "crm.lead"
CONTACT_PAGE_SIZE = 200
CALL_BATCH_SIZE = 500

# The Contacts list endpoint accepts `modified_after` only within this lookback.
# Incremental runs clamp to it. The full import deliberately does not, and
# instead verifies at runtime that the older floor it asked for was actually
# honoured — see `run_full_import`.
CONTACT_LOOKBACK_MAX_DAYS = 31
INCREMENTAL_CONTACT_LOOKBACK_DAYS = 30

# Bootstrap and catch-up overlap on the call timeline rather than abutting, so a
# call written while the bootstrap was running cannot fall through a seam left
# by clock skew between Odoo and VanillaSoft. Calls carry a provider-stable
# `call_history_id`, so the re-read is idempotent.
CATCHUP_OVERLAP = timedelta(minutes=5)


class CrmSyncLockedError(CrmAdapterError):
    """Another synchronization already holds this connection's advisory lock."""


class CrmFullImportArgumentError(CrmAdapterError):
    """`run_full_import` was given a missing or unusable historical bound."""


def advisory_lock_key(connection_id: int) -> str:
    """Session advisory-lock key for one connection (shared by cron and UI)."""
    return f"plasticos_crm_sync.connection.{connection_id}"


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _dt_naive_utc(value: str | None) -> datetime | None:
    dt = _parse_utc(value)
    return dt.replace(tzinfo=None) if dt else None


def _iso_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def completion_notice(run) -> tuple[str, str]:
    """``(notification type, message)`` for a run that finished without raising.

    A manual caller that treats every normal return as success would turn the
    ``failed`` / ``partial`` status this module now computes back into a green
    toast. The run row is the fact; this names it for the operator.
    """
    status = getattr(run, "status", None) or "unknown"
    if status == "success":
        return "success", "Sync finished"
    excerpt = str(getattr(run, "error_excerpt", "") or "").strip().splitlines()
    detail = excerpt[0] if excerpt else "see the run's error excerpt"
    if status == "failed":
        return "danger", f"Sync finished with failures: {detail}"
    return "warning", f"Sync finished {status}: {detail}"


def _forward_only(current: str | None, candidate: str) -> str | None:
    """Return `candidate`, or None when writing it would rewind `current`.

    A full import replays history the incremental path already consumed, so its
    per-page watermark writes are older than what the connection already holds.
    Letting them land would reset a valid watermark and make the next
    `run_connection` re-read months of source data. Unparseable values fall
    through to the caller's write, preserving the pre-existing behaviour.
    """
    cur = _parse_utc(current)
    new_dt = _parse_utc(candidate)
    if cur and new_dt and new_dt <= cur:
        return None
    return candidate


# Per-record outcome classification (odoo-intent-1 ingestion milestone).
# Every source record is deterministically classified; failures are recorded
# per record (never silent loss) and persisted on plasticos.crm.sync.run.
# ``deferred`` is the call-only outcome for a row buffered as an orphan (its
# lead is not imported yet): the durable orphan record keeps the row, the
# run's ``orphans_buffered`` counter persists the count, and the shared
# summary reports it as not-yet-landed — so every seen row is accounted
# exactly once and never mistaken for a successful write.
OUTCOME_FIELDS = ("created", "updated", "unchanged", "duplicate_rejected", "failed", "deferred")
# Outcomes after which a lead is admitted: identity resolved without conflict
# and the row landed (or already matched). Only these may receive dependent
# writes (custom-table rows, calls). ``duplicate_rejected`` and ``failed``
# must produce zero child-table side effects.
ADMITTED_OUTCOMES = ("created", "updated", "unchanged")

# Exact tokens only. "USA" must not match "USA Minor Outlying Islands" by substring.
_US_COUNTRY_ALIASES = frozenset(
    {
        "us",
        "usa",
        "united states",
        "united states of america",
    }
)


def _collapse_ws(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _split_material_values(value) -> list[str]:
    text = str(value or "").replace("|", "\n").replace(";", "\n")
    return [part for part in (_collapse_ws(piece) for piece in text.splitlines()) if part]


def _material_field_kind(label: str) -> str:
    if label in {"materials", "material"} or label.startswith("material ("):
        return "phrase"
    if label in {"material form", "material type", "form"} or label.startswith("form ("):
        return "hint"
    return ""


def _material_inputs(*field_maps):
    phrases = []
    hints = {}
    weak = []
    for fields in field_maps:
        for key, value in (fields or {}).items():
            label = _collapse_ws(key).casefold()
            parts = _split_material_values(value)
            kind = _material_field_kind(label)
            if kind == "phrase":
                phrases.extend(parts)
            elif kind == "hint":
                if parts:
                    hints[label] = parts[0]
                weak.extend(parts)
    return _dedupe_phrases(phrases), hints, _dedupe_phrases(weak)


def _dedupe_phrases(phrases) -> list[str]:
    seen = set()
    kept = []
    for phrase in phrases:
        key = phrase.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(phrase)
    return kept


def _facility_for_material(lead):
    """Existing facility only. A missing or ambiguous facility is not created.

    A standalone company is a facility when the partner model says so. A parent
    with one child facility resolves to that child. Several children stay unresolved.
    """
    partner = lead.partner_id
    if not partner:
        return None, "facility unresolved"
    if partner.is_facility:
        return partner, ""
    parent = partner.parent_id
    if parent and parent.is_company and parent.parent_id:
        return parent, ""
    children = partner.child_ids.filtered(lambda child: child.is_company)
    if len(children) == 1:
        return children, ""
    if len(children) > 1:
        return None, "facility unresolved: ambiguous child facilities"
    return None, "facility unresolved"


def _country_token(value: str) -> str:
    return _collapse_ws(value).casefold()


def _new_outcomes() -> dict[str, int]:
    return {"seen": 0, "table_rows": 0, **{key: 0 for key in OUTCOME_FIELDS}}


def _merge_outcomes(target: dict[str, int], source: dict[str, int] | None) -> dict[str, int]:
    if not source:
        return target
    for key, value in source.items():
        if isinstance(value, int):
            target[key] = target.get(key, 0) + value
    return target


def _write_contact_counters(run, seen: int, outcomes: dict[str, int], base: dict[str, int] | None = None) -> None:
    """Persist contact classification counters (called inside the page
    transaction, so a page rollback reverts these writes with the records)."""
    run.contacts_seen = (base.get("seen", 0) if base else 0) + seen
    run.contacts_created = (base.get("created", 0) if base else 0) + outcomes["created"]
    run.contacts_updated = (base.get("updated", 0) if base else 0) + outcomes["updated"]
    run.contacts_unchanged = (base.get("unchanged", 0) if base else 0) + outcomes["unchanged"]
    run.contacts_duplicate_rejected = (base.get("duplicate_rejected", 0) if base else 0) + outcomes[
        "duplicate_rejected"
    ]
    run.contacts_failed = (base.get("failed", 0) if base else 0) + outcomes["failed"]
    run.table_rows_upserted = (base.get("table_rows", 0) if base else 0) + outcomes["table_rows"]


def _write_call_counters(run, seen: int, outcomes: dict[str, int], base: dict[str, int] | None = None) -> None:
    run.calls_seen = (base.get("seen", 0) if base else 0) + seen
    run.calls_created = (base.get("created", 0) if base else 0) + outcomes["created"]
    run.calls_updated = (base.get("updated", 0) if base else 0) + outcomes["updated"]
    run.calls_unchanged = (base.get("unchanged", 0) if base else 0) + outcomes["unchanged"]
    run.calls_failed = (base.get("failed", 0) if base else 0) + outcomes["failed"]


def _differs(record, field_name: str, value) -> bool:
    """True when writing ``value`` would actually change ``record``.

    Tolerant of plain-object fakes in the pure-python tier: records without a
    ``_fields`` registry are compared attribute-wise.
    """
    fields = getattr(record, "_fields", None) or None
    if fields is not None and field_name not in fields:
        return False
    try:
        current = record[field_name]
    except (KeyError, TypeError):
        current = getattr(record, field_name, None)
    if hasattr(current, "id"):
        current = current.id or False
    return current != (value if value is not None else False)


class SyncOrchestrator:
    def __init__(self, env):
        self.env = env
        # Reset by every `_sync_contacts` pass; read by `run_full_import` as the
        # evidence that the requested historical floor was actually served.
        self.oldest_contact_modified_seen: datetime | None = None
        # Per-record classification accumulator, open only while a sync pass is
        # processing a page; per-record duplicate/failed details collected
        # during a run feed the shared import-run-summary errors.
        self.outcomes: dict[str, int] | None = None
        self.error_rows: list[dict[str, str]] = []
        # Classification of the most recent `_upsert_lead` call. `_upsert_lead`
        # returns a lead recordset for admitted AND rejected outcomes (pinned
        # contract), so callers gate dependent writes on this, never on the
        # returned record.
        self.last_lead_outcome: str | None = None

    def run_connection(self, connection) -> Any:
        connection.ensure_one()
        connection_id = connection.id
        self._ensure_caller_state_durable()
        # I5 — session advisory lock at the single choke point, so the cron and
        # the manual `action_sync_now` button exclude each other. Session locks
        # survive the page commits below (they are not transaction-scoped) and
        # are re-entrant within one backend session, so the cron's own outer
        # lock nests harmlessly.
        lock_key = advisory_lock_key(connection_id)
        if not self._try_advisory_lock(lock_key):
            raise CrmSyncLockedError(f"CRM sync already running for connection {connection_id}")
        try:
            # Scope is fixed before the audit row exists, so the row names what
            # this run asked the provider for even when it fails on the first
            # remote call. A run must read as "the rolling window" or "the
            # operator's floors" — never as an implied historical census.
            now = datetime.now(UTC)
            contact_from, clamped_from = self._incremental_contact_scope(connection)
            call_from = self._incremental_call_start(connection, now)
            # I2 — the audit record must exist independently of the fallible
            # remote work it describes, so create it on an owned cursor that
            # commits before the first adapter call.
            run_id = self._create_sync_run_durable(
                connection_id,
                {
                    "kind": "incremental",
                    "contact_scope_from_utc": contact_from,
                    "call_scope_from_utc": _iso_z(call_from),
                    "call_scope_to_utc": _iso_z(now),
                },
            )
            # That row was created and committed on a SECOND cursor. Odoo runs
            # cursors at REPEATABLE READ, and this transaction's snapshot was
            # taken by the advisory-lock SELECT above — before the row existed.
            # Without ending the transaction here, browse(run_id) is not in this
            # snapshot: .exists() is False and every write to it is an
            # "UPDATE ... WHERE id=N" matching zero rows, silently. Committing
            # starts a new transaction whose snapshot includes the row.
            # pg_try_advisory_lock is SESSION-scoped, so the lock survives this
            # commit exactly as it survives the page commits below (I5).
            self.env.cr.commit()
            run = self.env["plasticos.crm.sync.run"].browse(run_id)
            try:
                adapter = self._build_adapter(connection)
                adapter.healthcheck()
                contacts_n = self._sync_contacts(connection, adapter, run, modified_after_override=contact_from)
                calls_n = self._sync_calls(connection, adapter, run, start_override=call_from, end_override=now)
                resolved = self._resolve_orphans(connection, adapter, run)
                notes = [self._lookback_clamp_note(clamped_from, contact_from)] if clamped_from else []
                status, excerpt = self._completion(run, notes)
                run.write(
                    {
                        "status": status,
                        "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        "contacts_upserted": contacts_n,
                        "calls_upserted": calls_n,
                        "orphans_resolved": resolved,
                        "error_excerpt": excerpt,
                    }
                )
                connection_vals: dict[str, Any] = {"last_error": excerpt}
                if status != "failed":
                    connection_vals["last_success_at"] = datetime.now(UTC).replace(tzinfo=None)
                connection.write(connection_vals)
                # Land this connection's outcome before the caller (cron) moves
                # to the next one: a later connection's rollback must not erase
                # a successful run that already happened.
                self.env.cr.commit()
            except (CrmAdapterError, Exception) as exc:
                # I3 — capture primitives, then release every row this
                # transaction still holds BEFORE opening the failure cursor.
                # `_sync_contacts`/`_sync_calls` may leave an uncommitted write
                # on the sync-run row; a second cursor updating that same row
                # would wait on transaction A and hang the RPC.
                excerpt = str(exc)[:2000]
                _logger.exception("CRM sync failed connection=%s", connection_id)
                self.env.cr.rollback()
                # Recordset state from before the rollback is not trustworthy —
                # the durable write below re-browses from primitive ids only.
                self._persist_sync_failure_durable(connection_id, run_id, excerpt)
                raise
        finally:
            self._advisory_unlock(lock_key)
        return self.env["plasticos.crm.sync.run"].browse(run_id)

    def run_full_import(
        self,
        connection,
        call_history_floor: str,
        contact_modified_floor: str | None = None,
    ) -> Any:
        """Manual one-shot bootstrap, then hand off to the incremental path.

        `run_connection` is a rolling catch-up: it clamps contacts to the list
        endpoint's 30-day lookback and calls to a 7-day window, so on an empty
        database it produces a partial CRM, not a populated one. This method is
        the explicit "populate it once" operation an operator runs from the Odoo
        shell before switching to `run_connection`.

        Three phases inside one advisory lock and one sync-run audit row:

        1. contacts from `contact_modified_floor` (defaults to the call floor),
           with no rolling clamp;
        2. call history from `call_history_floor` to a UTC boundary captured
           BEFORE phase 1 started;
        3. the ordinary incremental logic, unchanged, which closes the window
           between that boundary and now — so a contact or call mutated while
           phase 1 was running cannot fall into a gap.

        On success the connection's watermarks are left exactly where an
        immediate `run_connection(connection)` continues from, and every write
        is keyed on provider identity, so the replay creates no duplicates.

        Completeness is verified, not assumed: see `_contact_enumeration_gap`.
        """
        connection.ensure_one()
        self._ensure_caller_state_durable()
        connection_id = connection.id
        # Validate every bound BEFORE any lock, audit row or remote call — an
        # unusable floor must not leave a half-run behind to interpret.
        call_floor = self._require_utc_bound(call_history_floor, "call_history_floor")
        contact_floor_dt = (
            self._require_utc_bound(contact_modified_floor, "contact_modified_floor")
            if contact_modified_floor is not None
            else call_floor
        )
        contact_floor = _iso_z(contact_floor_dt)

        lock_key = advisory_lock_key(connection_id)
        if not self._try_advisory_lock(lock_key):
            raise CrmSyncLockedError(f"CRM sync already running for connection {connection_id}")
        try:
            # Same I2 ordering as run_connection: the audit row is durable on an
            # owned cursor before the first fallible remote call, and it names
            # the operator's floors so the ledger shows this was the bootstrap.
            run_id = self._create_sync_run_durable(
                connection_id,
                {
                    "kind": "full_import",
                    "contact_scope_from_utc": contact_floor,
                    "call_scope_from_utc": _iso_z(call_floor),
                },
            )
            self.env.cr.commit()
            run = self.env["plasticos.crm.sync.run"].browse(run_id)
            try:
                adapter = self._build_adapter(connection)
                adapter.healthcheck()

                # Captured before enumeration: everything after this instant is
                # phase 3's responsibility, so a mutation racing the bootstrap
                # is covered by one phase or the other, never by neither.
                boundary = datetime.now(UTC)

                bootstrap_contacts = self._sync_contacts(
                    connection,
                    adapter,
                    run,
                    modified_after_override=contact_floor,
                )
                gap = self._contact_enumeration_gap(contact_floor_dt, boundary)
                # Capture before the catch-up pass resets it — this is the
                # bootstrap's evidence, and the only one that means anything.
                oldest_seen = self.oldest_contact_modified_seen

                bootstrap_calls = self._sync_calls(
                    connection,
                    adapter,
                    run,
                    start_override=call_floor,
                    end_override=boundary,
                )

                catchup_contacts = self._sync_contacts(
                    connection,
                    adapter,
                    run,
                    counter_base=bootstrap_contacts,
                    outcome_base=self._contact_outcomes,
                )
                catchup_end = datetime.now(UTC)
                catchup_calls = self._sync_calls(
                    connection,
                    adapter,
                    run,
                    start_override=boundary - CATCHUP_OVERLAP,
                    end_override=catchup_end,
                    counter_base=bootstrap_calls,
                    outcome_base=self._call_outcomes,
                )
                resolved = self._resolve_orphans(connection, adapter, run)
                status, excerpt = self._completion(run, [gap] if gap else [])

                run.write(
                    {
                        "status": status,
                        "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        "contacts_upserted": bootstrap_contacts + catchup_contacts,
                        "calls_upserted": bootstrap_calls + catchup_calls,
                        "orphans_resolved": resolved,
                        "error_excerpt": excerpt,
                        "call_scope_to_utc": _iso_z(catchup_end),
                    }
                )
                connection_vals: dict[str, Any] = {"last_error": excerpt}
                if status != "failed":
                    connection_vals["last_success_at"] = datetime.now(UTC).replace(tzinfo=None)
                connection.write(connection_vals)
                self.env.cr.commit()
                _logger.info(
                    "CRM full import connection=%s contacts=%s calls=%s status=%s "
                    "contact_floor=%s call_floor=%s boundary=%s oldest_contact_modified=%s",
                    connection_id,
                    bootstrap_contacts + catchup_contacts,
                    bootstrap_calls + catchup_calls,
                    status,
                    contact_floor,
                    _iso_z(call_floor),
                    _iso_z(boundary),
                    _iso_z(oldest_seen) if oldest_seen else "none",
                )
            except (CrmAdapterError, Exception) as exc:
                # I3 — identical ordering to run_connection: roll back this
                # transaction's rows before the failure cursor touches them.
                excerpt = str(exc)[:2000]
                _logger.exception("CRM full import failed connection=%s", connection_id)
                self.env.cr.rollback()
                self._persist_sync_failure_durable(connection_id, run_id, excerpt)
                raise
        finally:
            self._advisory_unlock(lock_key)
        return self.env["plasticos.crm.sync.run"].browse(run_id)

    @staticmethod
    def _require_utc_bound(value: Any, name: str) -> datetime:
        """Parse a required historical bound, or refuse to start.

        A full import that silently fell back to the rolling default would
        report success over a fraction of the history the operator asked for,
        which is worse than not running: the watermarks would then declare that
        history consumed.
        """
        if value is None or (isinstance(value, str) and not value.strip()):
            raise CrmFullImportArgumentError(
                f"{name} is required for a full import — pass an explicit ISO-8601 UTC "
                "instant (e.g. '2019-01-01T00:00:00Z'); there is no safe default"
            )
        parsed: datetime | None
        if isinstance(value, datetime):
            parsed = value if value.tzinfo else value.replace(tzinfo=UTC)
            parsed = parsed.astimezone(UTC)
        else:
            parsed = _parse_utc(str(value))
        if parsed is None:
            raise CrmFullImportArgumentError(f"{name} is not a parseable ISO-8601 datetime: {value!r}")
        if parsed > datetime.now(UTC):
            raise CrmFullImportArgumentError(f"{name} is in the future: {value!r}")
        return parsed

    def _contact_enumeration_gap(self, contact_floor: datetime, boundary: datetime) -> str | None:
        """Return why the contact census is unproven, or None when it is proven.

        The list endpoint documents a 31-day maximum on `modified_after`.
        The full import asks for an older floor anyway, because the two failure
        modes differ sharply:

        * the provider rejects the out-of-range bound — a `CrmAdapterError`,
          the run fails, no watermark moves, nothing is claimed;
        * the provider silently clamps it — the run "succeeds" over the last
          31 days while reporting a full census. That is the one outcome
          this method exists to prevent.

        Seeing at least one contact modified before the lookback horizon proves
        the older floor was served. Seeing none is genuinely ambiguous — the
        dataset may simply have no contact that old — so the run is reported
        `partial` with the ambiguity named, never `success`.
        """
        if contact_floor >= boundary - timedelta(days=CONTACT_LOOKBACK_MAX_DAYS):
            # Floor inside the documented lookback: nothing to prove.
            return None
        oldest = self.oldest_contact_modified_seen
        horizon = boundary - timedelta(days=CONTACT_LOOKBACK_MAX_DAYS)
        if oldest is not None and oldest < horizon:
            return None
        return (
            "Contact census unproven: requested modified_after "
            f"{_iso_z(contact_floor)}, which is older than the {CONTACT_LOOKBACK_MAX_DAYS}-day "
            f"Contacts lookback (horizon {_iso_z(horizon)}), and no returned contact was modified "
            f"before that horizon (oldest seen: {_iso_z(oldest) if oldest else 'none'}). "
            "The provider may have silently clamped the floor, so contacts untouched since "
            f"{_iso_z(horizon)} may be missing. Reconcile the imported lead count against "
            "VanillaSoft's own project contact count before treating this import as complete."
        )

    def _incremental_contact_scope(self, connection) -> tuple[str, str | None]:
        """Return ``(modified_after to request, watermark it was clamped from)``.

        The Contacts endpoint accepts ``modified_after`` only inside its rolling
        lookback, so a watermark older than that is clamped forward. The clamp
        is a scope limitation the run must name: every modification between
        the watermark and the clamped bound is never requested, and the
        watermark then moves past it. The second element is ``None`` when the
        connection held no watermark — a fresh connection asks for the default
        window and drops nothing it had ever acknowledged.
        """
        requested = connection.default_contact_modified_after()
        floor = datetime.now(UTC) - timedelta(days=INCREMENTAL_CONTACT_LOOKBACK_DAYS)
        parsed = _parse_utc(requested)
        if parsed and parsed < floor:
            return _iso_z(floor), (requested if connection.contact_watermark_utc else None)
        return requested, None

    @staticmethod
    def _incremental_call_start(connection, now: datetime) -> datetime:
        """Start of the rolling call window: the watermark, else the backfill
        floor, else seven days — the pre-existing defaults, in one place so the
        audit row and the sync pass cannot disagree about what was asked."""
        if connection.call_watermark_utc:
            return _parse_utc(connection.call_watermark_utc) or (now - timedelta(days=7))
        if connection.call_backfill_floor_utc:
            return _parse_utc(connection.call_backfill_floor_utc) or (now - timedelta(days=30))
        return now - timedelta(days=7)

    @staticmethod
    def _lookback_clamp_note(clamped_from: str, requested: str) -> str:
        return (
            f"Contact scope limited: the connection's contact watermark {clamped_from} is older than the "
            f"{INCREMENTAL_CONTACT_LOOKBACK_DAYS}-day Contacts lookback, so this run requested modified_after "
            f"{requested} instead. Contacts modified between {clamped_from} and {requested} were not requested "
            "from the provider and the watermark has moved past them. Run the full import "
            "(make import-vanillasoft with explicit floors) to reconcile that range."
        )

    def _completion(self, run, notes: list[str]) -> tuple[str, str | bool]:
        """Classify a run that finished without raising, from what it recorded.

        Mirrors ``import_summary.build_run_summary``: a per-record write
        failure is ``failed``; an identity conflict, a buffered orphan call or
        a named scope limitation is ``partial``; only a run with none of those
        is ``success``. The run row is what the operator sees first, so it must
        never read greener than the shared summary built from the same counters.
        """

        def count(name: str) -> int:
            return getattr(run, name, 0) or 0

        failed_contacts = count("contacts_failed")
        failed_calls = count("calls_failed")
        duplicates = count("contacts_duplicate_rejected")
        deferred = count("orphans_buffered")
        lines = list(notes)
        if failed_contacts or failed_calls:
            lines.append(
                f"{failed_contacts} contact(s) and {failed_calls} call(s) failed to write; "
                "each failure is counted on this run, none was dropped."
            )
            for row in self.error_rows[:5]:
                lines.append(f"  - {row.get('record_ref')}: {str(row.get('message'))[:200]}")
        if duplicates:
            lines.append(f"{duplicates} contact(s) rejected as identity conflicts (duplicate_rejected).")
        if deferred:
            lines.append(f"{deferred} call(s) buffered as orphans awaiting their lead; not landed yet.")
        if failed_contacts or failed_calls:
            status = "failed"
        elif lines:
            status = "partial"
        else:
            status = "success"
        excerpt = "\n".join(lines)[:2000]
        return status, (excerpt or False)

    def _try_advisory_lock(self, lock_key: str) -> bool:
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [lock_key])
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _advisory_unlock(self, lock_key: str) -> None:
        self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", [lock_key])

    def _ensure_caller_state_durable(self) -> None:
        """Commit the caller's transaction before this object opens its own cursor.

        I17. Every durable row these entrypoints create lives on a cursor of its
        own (`_create_sync_run_durable`), and `plasticos_crm_sync_run` carries a
        foreign key to the connection. PostgreSQL cannot see a row the caller's
        transaction has not committed, so a connection created by the caller and
        handed straight in makes that INSERT fail the foreign key — the
        first-run Settings path, where the operator's very first sync creates
        the connection and syncs it in one RPC.

        `flush()` cannot substitute: it writes the INSERT inside the caller's
        transaction, where a second connection still cannot read it. Only a
        commit makes the row visible to a transaction this process does not own.
        `Cursor.commit()` flushes first, so the pending INSERT lands.

        The precondition belongs to the code that opens the independent cursor
        rather than to each caller, so both public entrypoints assert it here.
        Callers that reach this point have finished the work they wanted
        durable: the Settings action has already run `set_values()`, and the
        cron holds nothing pending.
        """
        self.env.cr.commit()

    def _create_sync_run_durable(self, connection_id: int, vals: dict[str, Any] | None = None) -> int:
        """Create the sync-run audit row on an owned cursor and commit it.

        Committing the ambient RPC cursor is unsafe (Odoo owns it), so the
        durable audit state gets its own transaction. ``vals`` carries the
        run's kind and requested scope, durable with the row itself so a run
        that fails before its first page still says what it asked for.
        Returns the primitive id.
        """
        from odoo import api

        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            # Before this row exists: the caller holds the connection's session
            # advisory lock, so any row still `running` belongs to a process
            # that died without recording a completion (see the helper).
            self._close_interrupted_runs(env, connection_id)
            run = env["plasticos.crm.sync.run"].create(
                {
                    "connection_id": connection_id,
                    "status": "running",
                    "started_at": datetime.now(UTC).replace(tzinfo=None),
                    **(vals or {}),
                }
            )
            run_id = run.id
            cr.commit()
        return run_id

    @staticmethod
    def _close_interrupted_runs(env, connection_id: int) -> int:
        """Close this connection's ``running`` rows that nothing is running.

        A worker kill, an OOM or a deploy restart ends the process between the
        audit row's ``running`` and any completion write, and neither
        ``_persist_sync_failure_durable`` nor the success write ever runs. The
        row then reads as in progress forever, and nothing in the ledger says
        the remainder of its scope was never consumed.

        The connection's advisory lock is session-scoped and dies with the
        backend that held it, so the next run that holds it has proof that no
        other synchronization is in flight for this connection: every row still
        ``running`` here is interrupted. It is closed as ``failed`` — the
        existing status for a run that did not complete its scope — with the
        interruption named. Counters and watermarks are left exactly as the
        interrupted run committed them, which is why the next run resumes from
        the right place; this only makes the status say so.

        Called on the owned cursor that inserts the next audit row, before that
        insert, so the new ``running`` row is never caught by its own sweep.
        """
        Run = env["plasticos.crm.sync.run"]
        finished = datetime.now(UTC).replace(tzinfo=None)
        closed = 0
        for row in Run.search([("connection_id", "=", connection_id), ("status", "=", "running")]):
            row.write(
                {
                    "status": "failed",
                    "finished_at": finished,
                    "error_excerpt": (
                        "Interrupted: this run recorded no completion and no other synchronization holds "
                        "the connection lock, so its process ended before it finished. Counters show "
                        "committed work only; the unprocessed remainder of its scope was never acknowledged "
                        "and the next run resumes from the committed watermarks."
                    ),
                }
            )
            closed += 1
        if closed:
            _logger.warning("CRM sync closed %s interrupted run(s) connection=%s", closed, connection_id)
        return closed

    def _persist_sync_failure_durable(self, connection_id: int, run_id: int | None, excerpt: str) -> None:
        """Write failed run + last_error on a clean owned cursor.

        Must be called only after the failed transaction has been rolled back —
        otherwise this cursor blocks on rows transaction A still holds.

        Writes only the fields a failure changes. The counters are deliberately
        absent: `_sync_contacts`/`_sync_calls` already committed the true
        committed-work totals inside each page transaction, and the primitives
        available here describe the attempt, not what landed. Adding a counter
        to this dict would overwrite a correct durable value with a stale or
        zero one — the exact undercount this path is meant to preserve.
        """
        from odoo import api

        finished = datetime.now(UTC).replace(tzinfo=None)
        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            if run_id:
                run = env["plasticos.crm.sync.run"].browse(run_id).exists()
                if run:
                    run.write(
                        {
                            "status": "failed",
                            "finished_at": finished,
                            "error_excerpt": excerpt,
                        }
                    )
            connection = env["plasticos.crm.connection"].browse(connection_id).exists()
            if connection:
                connection.write({"last_error": excerpt})
            cr.commit()

    def upsert_contact_external_id(self, connection, external_id: str) -> Any:
        """Single-contact path: contact + call history + custom tables."""
        self._load_approved_crosswalk()
        adapter = self._build_adapter(connection)
        lead_dto = adapter.get_contact(str(external_id))
        if not lead_dto:
            raise CrmAdapterError(f"Contact {external_id} not found")
        reason_at = len(self.error_rows)
        lead = self._upsert_lead(connection, lead_dto, adapter)
        calls_n = 0
        if self.last_lead_outcome in ADMITTED_OUTCOMES:
            if hasattr(adapter, "iter_calls_for_contact"):
                for batch in adapter.iter_calls_for_contact(str(external_id)):
                    calls_n += self._upsert_calls(connection, batch, None)
            self._sync_tables_for_lead(connection, adapter, lead_dto.external_id, lead)
        else:
            # Identity conflict or write failure: no dependent writes may hang
            # off an unadmitted lead (they would attach to an arbitrary match).
            reasons = [str(row.get("message") or "") for row in self.error_rows[reason_at:] if row.get("message")]
            _logger.warning(
                "Single-contact sync skipped dependent writes external_id=%s outcome=%s reason=%s",
                external_id,
                self.last_lead_outcome,
                "; ".join(reasons) or "no reason recorded",
            )
        self._resolve_orphans(connection, adapter, None)
        _logger.info(
            "Single-contact sync done external_id=%s lead_id=%s calls=%s",
            external_id,
            lead.id if lead else False,
            calls_n,
        )
        return lead

    def _build_adapter(self, connection):
        icp = self.env["ir.config_parameter"].sudo()
        api_key = (icp.get_param("plasticos_crm_sync.vanillasoft_api_key") or "").strip()
        root = (
            icp.get_param("plasticos_crm_sync.vanillasoft_root_endpoint") or ""
        ).strip() or "https://vanillasoft.net"
        project = (connection.project_id or icp.get_param("plasticos_crm_sync.vanillasoft_project_id") or "").strip()
        return get_adapter(
            connection.provider,
            api_key=api_key,
            root_endpoint=root,
            project_id=int(project or 0),
        )

    def _sync_contacts(
        self,
        connection,
        adapter,
        run,
        modified_after_override: str | None = None,
        counter_base: int = 0,
        outcome_base: dict[str, int] | None = None,
    ) -> int:
        if modified_after_override:
            # An explicit bound from the caller: the full import's operator
            # floor, which the rolling clamp must not silently shorten back to
            # 30 days, or `run_connection`'s already-clamped incremental bound,
            # which is also what its audit row recorded. In both cases
            # `oldest_contact_modified_seen` is what proves afterwards whether
            # the provider honoured it (see `run_full_import`).
            modified_after = modified_after_override
        else:
            modified_after, _clamped_from = self._incremental_contact_scope(connection)
        self.oldest_contact_modified_seen = None
        self._load_approved_crosswalk()

        # `committed` counts rows this method has durably landed; `pending`
        # counts rows written into the still-open transaction. The sync-run
        # counter must describe committed work, so it is written INTO the page
        # transaction (before its commit) and `committed` only advances once
        # that commit has returned. A later page's failure rolls back `pending`
        # and the ambient counter write with it, leaving the last committed
        # value on the row — which is the number that is actually true.
        committed = 0
        pending = 0
        committed_outcomes = _new_outcomes()
        last_batch_end = None
        for leads, batch_end, _partial in adapter.iter_contacts(
            modified_after=modified_after,
            limit=CONTACT_PAGE_SIZE,
        ):
            page_n = 0
            self.outcomes = _new_outcomes()
            for dto in leads:
                lead = self._upsert_lead(connection, dto, adapter)
                # Dependent table rows only after unambiguous admission: a
                # duplicate_rejected or failed contact gets no child writes.
                if self.last_lead_outcome in ADMITTED_OUTCOMES and not dto.deleted:
                    self._sync_tables_for_lead(connection, adapter, dto.external_id, lead)
                self._observe_contact_modified(dto)
                page_n += 1
            self.outcomes["seen"] = len(leads)
            pending += page_n
            if batch_end:
                last_batch_end = batch_end
                forward = _forward_only(connection.contact_watermark_utc, batch_end)
                if forward:
                    connection.contact_watermark_utc = forward
                if run:
                    run.contacts_upserted = counter_base + committed + pending
                    totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
                    _write_contact_counters(run, totals["seen"], totals, base=outcome_base)
                self.env.cr.commit()  # records + watermark + counters, one page
                committed += pending
                pending = 0
                _merge_outcomes(committed_outcomes, self.outcomes)
                self.outcomes = _new_outcomes()
        totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
        self.outcomes = None
        if last_batch_end:
            forward = _forward_only(connection.contact_watermark_utc, last_batch_end)
            if forward:
                connection.contact_watermark_utc = forward
        if run:
            # Any trailing `pending` is committed by run_connection's success
            # commit; on the failure path this write is rolled back with it.
            run.contacts_upserted = counter_base + committed + pending
            _write_contact_counters(run, totals["seen"], totals, base=outcome_base)
        self._contact_outcomes = totals
        return committed + pending

    def _observe_contact_modified(self, dto: CanonicalLead) -> None:
        """Track the oldest source `modified` timestamp this pass actually saw.

        A full import claims to have reached back to its floor. That claim is
        only evidence if some contact older than the list endpoint's own
        lookback came back — see `run_full_import`.
        """
        modified = _parse_utc(dto.modified_utc)
        if not modified:
            return
        current = self.oldest_contact_modified_seen
        if current is None or modified < current:
            self.oldest_contact_modified_seen = modified

    def _sync_calls(
        self,
        connection,
        adapter,
        run,
        start_override: datetime | None = None,
        end_override: datetime | None = None,
        counter_base: int = 0,
        outcome_base: dict[str, int] | None = None,
    ) -> int:
        now = datetime.now(UTC)
        end = end_override or now
        if start_override is not None:
            # An explicit, already-validated bound from the caller: the full
            # import's historical floor, or the incremental start the audit row
            # recorded. The short rolling defaults must not silently replace it.
            start = start_override
        else:
            start = self._incremental_call_start(connection, now)

        # Window size: 1 day chunks to keep batches manageable
        # Same committed-vs-attempted split as _sync_contacts: the counter is
        # written into the batch transaction, and `committed` advances only
        # after that commit returns.
        committed = 0
        committed_outcomes = _new_outcomes()
        cursor = start
        while cursor < end:
            window_end = min(cursor + timedelta(days=1), end)
            for batch in adapter.iter_calls(
                start=_iso_z(cursor),
                end=_iso_z(window_end),
                limit=CALL_BATCH_SIZE,
            ):
                self.outcomes = _new_outcomes()
                self.outcomes["seen"] = len(batch)
                batch_n = self._upsert_calls(connection, batch, run)
                if run:
                    run.calls_upserted = counter_base + committed + batch_n
                    totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
                    _write_call_counters(run, totals["seen"], totals, base=outcome_base)
                self.env.cr.commit()  # batch commit
                committed += batch_n
                _merge_outcomes(committed_outcomes, self.outcomes)
                self.outcomes = _new_outcomes()
            forward = _forward_only(connection.call_watermark_utc, _iso_z(window_end))
            if forward:
                connection.call_watermark_utc = forward
            self.env.cr.commit()  # watermark advance
            cursor = window_end
        totals = _merge_outcomes(_merge_outcomes(_new_outcomes(), committed_outcomes), self.outcomes)
        self.outcomes = None
        if run:
            run.calls_upserted = counter_base + committed
            _write_call_counters(run, totals["seen"], totals, base=outcome_base)
        self._call_outcomes = totals
        return committed

    def _load_approved_crosswalk(self) -> None:
        """Read the pinned CSV before any approved identity write.

        An unset parameter leaves the existing importer in place. A set
        parameter that fails the pinned digest aborts before those writes.
        """
        if getattr(self, "_crosswalk_ready", False):
            return
        try:
            self._crosswalk = without_duplicate_contacts(load_crosswalk_map(self.env))
        except CrosswalkError as exc:
            self._crosswalk = None
            self._crosswalk_ready = False
            raise CrmAdapterError(str(exc)) from exc
        self._crosswalk_ready = True

    def _approved_ct_id(self, external_id: str) -> str | None:
        mapping = getattr(self, "_crosswalk", None) or {}
        return mapping.get(str(external_id))

    def _find_person_ref(self, provider: str, external_id: str):
        ref = self.env["plasticos.crm.external.ref"].search(
            [
                ("provider", "=", provider),
                ("external_id", "=", external_id),
                ("res_model", "=", "res.partner"),
            ],
            limit=1,
        )
        if not ref or not getattr(ref, "id", False):
            return self.env["plasticos.crm.external.ref"].browse()
        return ref

    def _erp_person_for_ct(self, ct_id: str):
        marker = f"{XMLID_MODULE}.{xmlid_name(ct_id)}"
        imd = self.env["ir.model.data"].sudo()  # XMLID rows are system data the sync user must read
        rows = imd.search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "=", xmlid_name(ct_id)),
                ("model", "=", "res.partner"),
            ]
        )
        if len(rows) != 1:
            return None, f"ERP marker {marker} resolved {len(rows)} rows"
        partner = (
            self.env["res.partner"].sudo().with_context(active_test=False).browse(rows.res_id).exists()
        )  # archived ERP people are hidden by the default active test
        if len(partner) != 1:
            return None, f"ERP marker {marker} does not point at one partner"
        if partner.is_company:
            return None, f"ERP marker {marker} points at a company"
        return partner, ""

    def _add_approved_phones(self, partner, dto: CanonicalLead) -> bool:
        """Add missing CRM numbers as phone lines. Never assign phone or mobile.

        ERP and CRM values are normalized to the same key before the comparison.
        """
        Phone = self.env["plasticos.partner.phone"].sudo()  # cron user has no facility-phone ACL; lines are additive
        present = {phone_match_key(partner.phone or "")}
        has_mobile = False
        for line in partner.phone_line_ids:
            present.add(phone_match_key(line.number or ""))
            if line.label == "mobile":
                has_mobile = True
        present.discard("")
        numbers = list(dto.phone_numbers or ())
        mobiles = {phone_match_key(number) for number in (dto.mobile_numbers or ())}
        for extra, kind in ((dto.phone, "other"), (dto.mobile, "mobile")):
            token = phone_match_key(extra)
            if token and token not in {phone_match_key(number) for number in numbers}:
                numbers.append(extra)
                if kind == "mobile":
                    mobiles.add(token)
        wrote = False
        for number in numbers:
            token = phone_match_key(number)
            if not token or token in present:
                continue
            label = "mobile" if token in mobiles and not has_mobile else "other"
            Phone.create({"partner_id": partner.id, "label": label, "number": number})
            if label == "mobile":
                has_mobile = True
            present.add(token)
            wrote = True
        return wrote

    def _erp_company_for_cp(self, cp_id: str):
        marker = f"{XMLID_MODULE}.legacy_erp_cp_{cp_id}"
        imd = self.env["ir.model.data"].sudo()  # XMLID rows are system data the sync user must read
        rows = imd.search(
            [
                ("module", "=", XMLID_MODULE),
                ("name", "=", f"legacy_erp_cp_{cp_id}"),
                ("model", "=", "res.partner"),
            ]
        )
        if len(rows) != 1:
            return None, f"ERP marker {marker} resolved {len(rows)} rows"
        company = self.env["res.partner"].sudo().with_context(active_test=False).browse(rows.res_id).exists()
        if len(company) != 1 or not company.is_company:
            return None, f"ERP marker {marker} does not point at one company"
        return company, ""

    def _person_on_active_company(self, company, dto: CanonicalLead):
        """The VanillaSoft person on the active company. A same-named child is reused."""
        Partner = self.env["res.partner"].sudo().with_context(active_test=False)  # sync user cannot create partners
        name = " ".join(part for part in (_collapse_ws(dto.first_name), _collapse_ws(dto.last_name)) if part)
        children = Partner.search([("parent_id", "=", company.id), ("is_company", "=", False)])
        same = [
            child
            for child in children
            if name and _collapse_ws(getattr(child, "name", "")).casefold() == name.casefold()
        ]
        if len(same) == 1:
            return same[0]
        if len(same) > 1:
            return None
        return Partner.create(
            {
                "name": name or "Unknown",
                "parent_id": company.id,
                "is_company": False,
                "type": "contact",
                "email": (dto.email or "").strip() or False,
            }
        )

    def _bind_approved_contact(self, dto: CanonicalLead, ct_id: str):
        """Bind one approved ContactID onto the existing ERP person. No new lead.

        The CRM note is appended to the person's ``comment`` after the ERP notes.
        """
        outcomes = getattr(self, "outcomes", None)
        Lead = self.env[CRM_LEAD]
        partner, reason = self._erp_person_for_ct(ct_id)
        if partner is None:
            self._record_outcome(outcomes, "failed", dto.external_id, reason)
            self.last_lead_outcome = "failed"
            return Lead.browse()
        return self._bind_known_person(dto, partner)

    def _bind_known_person(self, dto: CanonicalLead, partner):
        """Bind one VanillaSoft contact onto a person already chosen. No new lead."""
        outcomes = getattr(self, "outcomes", None)
        Lead = self.env[CRM_LEAD]
        Ref = self.env["plasticos.crm.external.ref"]
        lead = self._find_lead(dto.provider, dto.external_id, Ref)
        matches = Lead.with_context(active_test=False).search([("vanillasoft_id", "=", dto.external_id)])
        if len(matches) > 1:
            self._record_outcome(outcomes, "duplicate_rejected", dto.external_id, "multiple leads carry the source id")
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        if lead and lead.partner_id and lead.partner_id.id not in (False, partner.id):
            self._record_outcome(
                outcomes, "duplicate_rejected", dto.external_id, "lead partner_id is a different partner"
            )
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        person_ref = self._find_person_ref(dto.provider, dto.external_id)
        if person_ref and person_ref.res_id not in (False, partner.id):
            self._record_outcome(
                outcomes, "duplicate_rejected", dto.external_id, "person external ref points at a different partner"
            )
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        wrote = False
        try:
            with self.env.cr.savepoint():
                if not person_ref:
                    Ref.create(
                        {
                            "provider": dto.provider,
                            "external_id": dto.external_id,
                            "res_model": "res.partner",
                            "res_id": partner.id,
                            "lead_id": False,
                        }
                    )
                    wrote = True
                elif person_ref.lead_id:
                    person_ref.write({"lead_id": False})
                    wrote = True
                if lead and not lead.partner_id:
                    lead.write({"partner_id": partner.id})
                    wrote = True
                if lead and dto.deleted:
                    lead.write({"active": False, "vanillasoft_sync_archived": True})
                    wrote = True
                elif lead and getattr(lead, "vanillasoft_sync_archived", False) and not dto.deleted:
                    lead.write({"active": True, "vanillasoft_sync_archived": False})
                    wrote = True
                comment = comment_with_note(partner.comment, dto.contact_note)
                if comment is not None:
                    partner.write({"comment": comment})
                    wrote = True
                if not dto.deleted and self._add_approved_phones(partner, dto):
                    wrote = True
        except Exception as exc:  # noqa: BLE001 - per-record failure is recorded, never silent loss
            self._record_outcome(outcomes, "failed", dto.external_id, str(exc))
            self.last_lead_outcome = "failed"
            return Lead.browse() if not lead else lead
        outcome = "updated" if wrote else "unchanged"
        if outcomes is not None:
            outcomes[outcome] += 1
        self.last_lead_outcome = outcome
        if lead and outcome in ADMITTED_OUTCOMES and not dto.deleted:
            self._apply_approved_materials(lead, dto.custom_fields)
        return lead or Lead.browse()

    def _keep_person_binding(self, dto: CanonicalLead, person_ref):
        """Honor an earlier approved bind when the crosswalk is not loaded.

        The persisted person ref is the approval record. Without the crosswalk
        nothing is enriched, and the legacy path must not mint a second lead or
        lead ref for the same source id. Conflicts are reported, never repaired.
        """
        outcomes = getattr(self, "outcomes", None)
        Lead = self.env[CRM_LEAD]
        partner = (
            self.env["res.partner"].sudo().with_context(active_test=False).browse(person_ref.res_id).exists()
        )  # archived ERP people keep their binding
        if not partner:
            self._record_outcome(outcomes, "failed", dto.external_id, "person external ref points at a missing partner")
            self.last_lead_outcome = "failed"
            return Lead.browse()
        lead = self._find_lead(dto.provider, dto.external_id, self.env["plasticos.crm.external.ref"])
        matches = Lead.with_context(active_test=False).search([("vanillasoft_id", "=", dto.external_id)])
        if len(matches) > 1:
            self._record_outcome(outcomes, "duplicate_rejected", dto.external_id, "multiple leads carry the source id")
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        if lead and lead.partner_id and lead.partner_id.id not in (False, partner.id):
            self._record_outcome(
                outcomes, "duplicate_rejected", dto.external_id, "lead partner_id is a different partner"
            )
            self.last_lead_outcome = "duplicate_rejected"
            return lead
        if outcomes is not None:
            outcomes["unchanged"] += 1
        self.last_lead_outcome = "unchanged"
        return lead or Lead.browse()

    def _apply_approved_materials(self, lead, *field_maps) -> None:
        """Attach material text only when one facility profile already exists.

        Same containment as ``_apply_contact_materials``: a material failure
        rolls back its own writes and is reported. The admitted identity, the
        page commit and the watermark are not affected.
        """
        try:
            with self.env.cr.savepoint():
                self._apply_resolved_approved_materials(lead, *field_maps)
        except Exception as exc:  # noqa: BLE001 - material failure must not drop the admitted contact
            _logger.warning("Approved material normalization failed for lead %s: %s", lead.id, exc)
            self.error_rows.append(
                {
                    "record_ref": lead.vanillasoft_id or str(lead.id or ""),
                    "message": f"material normalization failed: {exc}",
                }
            )

    def _apply_resolved_approved_materials(self, lead, *field_maps) -> None:
        phrases, hints, weak = _material_inputs(*field_maps)
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            normalize_material,
        )

        candidates = list(phrases)
        plain_hints = {}
        for label, value in hints.items():
            if normalize_material(self.env, value).polymer:
                candidates.append(value)
            else:
                plain_hints[label] = value
        texts = _dedupe_phrases(candidates) or list(weak)
        if not texts or not lead.partner_id:
            return
        partner, reason = _facility_for_material(lead)
        if partner is None:
            for text in texts:
                self.error_rows.append(
                    {"record_ref": lead.vanillasoft_id or str(lead.id), "message": f"{reason}: {text}"}
                )
            return
        profiles = self.env["plasticos.facility.profile"].search([("partner_id", "=", partner.id)])
        if len(profiles) != 1:
            for text in texts:
                self.error_rows.append(
                    {
                        "record_ref": lead.vanillasoft_id or str(lead.id),
                        "message": f"facility unresolved: {len(profiles)} profiles: {text}",
                    }
                )
            return
        self._store_normalized_materials(lead, texts, plain_hints, partner=partner)

    def _upsert_lead(self, connection, dto: CanonicalLead, adapter=None):
        """Identity-resolved lead upsert with deterministic classification.

        Returns the lead recordset (pinned contract for direct callers). When
        the caller opened an outcome accumulator (``self.outcomes``), this
        record is classified exactly one of
        ``created | updated | unchanged | duplicate_rejected | failed`` there:

        * ``unchanged`` — the normalized values already match; nothing written.
        * ``duplicate_rejected`` — the Odoo side holds conflicting identities
          for one source id (an external ref pointing at a different lead than
          the ``vanillasoft_id`` fallback finds, or several fallback matches).
          Refusing is the only honest choice: writing either would silently
          repoint identity, and creating would duplicate.
        * ``failed`` — the lead write or the external-reference write raised.
          Both run in one savepoint, so a failure leaves no partial identity.
          The record is reported, never silently dropped, and a later replay
          is not what repairs it.

        The classification is also left in ``self.last_lead_outcome`` so a
        caller can tell an admitted lead from a rejected one: the returned
        recordset alone cannot, because a rejected identity still returns the
        (ambiguous) match it found.
        """
        outcomes = getattr(self, "outcomes", None)
        self.last_lead_outcome = None
        approved = getattr(self, "_crosswalk", None) or {}
        if str(dto.external_id) in approved:
            ct_id = approved[str(dto.external_id)]
            if not ct_id:
                company_cp = ACTIVE_COMPANY_CP_BY_VS.get(str(dto.external_id))
                if company_cp:
                    company, reason = self._erp_company_for_cp(company_cp)
                    partner = self._person_on_active_company(company, dto) if company is not None else None
                    if partner is not None:
                        _logger.warning(
                            "Approved contact placed on active company external_id=%s cp_id=%s reason=%s",
                            dto.external_id,
                            company_cp,
                            "inactive contact is not the target",
                        )
                        return self._bind_known_person(dto, partner)
                    _logger.warning(
                        "Approved contact has no ERP person external_id=%s cp_id=%s reason=%s; importing as crm lead",
                        dto.external_id,
                        company_cp,
                        reason or "active company has more than one person with that name",
                    )
                else:
                    # The crosswalk keeps the VanillaSoft id and names no ERP contact.
                    # That contact is a lead. It is not attached to an inactive company.
                    _logger.warning(
                        "Approved contact has no ERP person external_id=%s reason=%s; importing as crm lead",
                        dto.external_id,
                        "crosswalk names no ERP contact",
                    )
            else:
                partner, reason = self._erp_person_for_ct(ct_id)
                if partner is not None:
                    return self._bind_approved_contact(dto, ct_id)
                # The approved CT_ID was not imported. It belongs only to an inactive
                # ERP contact or company. Do not bind that company. Keep the reason
                # and bring the VanillaSoft contact in as a lead.
                _logger.warning(
                    "Approved contact has no ERP person external_id=%s ct_id=%s reason=%s; importing as crm lead",
                    dto.external_id,
                    ct_id,
                    reason,
                )
                approved.pop(str(dto.external_id), None)
        person_ref = self._find_person_ref(dto.provider, dto.external_id)
        if person_ref:
            return self._keep_person_binding(dto, person_ref)
        Lead = self.env[CRM_LEAD]
        Ref = self.env["plasticos.crm.external.ref"]
        ref = Ref.search(
            [
                ("provider", "=", dto.provider),
                ("external_id", "=", dto.external_id),
                ("res_model", "=", CRM_LEAD),
            ],
            limit=1,
        )
        lead = Lead.browse(ref.res_id) if ref else Lead.browse()
        # `active_test=False`: a lead this sync archived for a provider deletion
        # is invisible to a default search, so the fallback would miss it and
        # create a duplicate the moment VanillaSoft restored the contact.
        if not lead:
            lead = Lead.with_context(active_test=False).search(
                [("vanillasoft_id", "=", dto.external_id)],
                limit=1,
            )
            # Identity-conflict detection: more than one lead carrying the same
            # source id is a duplicate to refuse, never to guess between.
            matches = Lead.with_context(active_test=False).search(
                [("vanillasoft_id", "=", dto.external_id)],
            )
            if len(matches) > 1:
                self._record_outcome(
                    outcomes, "duplicate_rejected", dto.external_id, "multiple leads carry the source id"
                )
                self.last_lead_outcome = "duplicate_rejected"
                return lead
        if ref and ref.res_id and lead.id != ref.res_id:
            self._record_outcome(outcomes, "duplicate_rejected", dto.external_id, "external ref and fallback disagree")
            self.last_lead_outcome = "duplicate_rejected"
            return lead

        vals = self._lead_vals_from_dto(dto)
        # Archival provenance, not a mirror of the provider flag. `active` is
        # shared state: Odoo users archive leads for their own reasons, and
        # `deleted=false` is the provider's steady state for every live contact,
        # so mirroring it would silently reopen every lead a user ever archived.
        # Reactivation is therefore conditional on THIS sync having been the one
        # that archived the lead.
        if dto.deleted:
            vals["active"] = False
            vals["vanillasoft_sync_archived"] = True
        elif lead and lead.vanillasoft_sync_archived:
            vals["active"] = True
            vals["vanillasoft_sync_archived"] = False

        prior_lead_id = lead.id if lead else False
        try:
            with self.env.cr.savepoint():
                if lead:
                    changed = {k: v for k, v in vals.items() if _differs(lead, k, v)}
                    if changed:
                        lead.write(changed)
                        outcome = "updated"
                    else:
                        outcome = "unchanged"
                else:
                    lead = Lead.create(vals)
                    outcome = "created"
                if outcome in ADMITTED_OUTCOMES:
                    if not ref:
                        Ref.create(
                            {
                                "provider": dto.provider,
                                "external_id": dto.external_id,
                                "res_model": CRM_LEAD,
                                "res_id": lead.id,
                                "lead_id": lead.id,
                            }
                        )
                    elif ref.res_id != lead.id or (getattr(ref.lead_id, "id", ref.lead_id) or False) != lead.id:
                        ref.write({"res_id": lead.id, "lead_id": lead.id})
        except Exception as exc:  # noqa: BLE001 - per-record failure is recorded, never silent loss
            if outcomes is not None:
                outcomes["failed"] += 1
            self.error_rows.append(
                {"record_ref": dto.external_id, "error_type": type(exc).__name__, "message": str(exc)}
            )
            self.last_lead_outcome = "failed"
            return Lead.browse(prior_lead_id) if prior_lead_id else Lead.browse()

        if outcomes is not None:
            outcomes[outcome] += 1
        self.last_lead_outcome = outcome
        if outcome in ADMITTED_OUTCOMES and not dto.deleted:
            self._apply_contact_materials(lead, dto.custom_fields)
        return lead

    def _record_outcome(self, outcomes: dict[str, int] | None, outcome: str, record_ref: str, message: str) -> None:
        """Keep the reason on every path. A counter is optional; the reason is not."""
        self.error_rows.append({"record_ref": record_ref, "message": message})
        if outcomes is not None:
            outcomes[outcome] += 1

    def _resolve_country_id(self, raw: str | None) -> int | bool:
        """Resolve a country by exact alias, ISO code, or exact name.

        ``USA`` is the United States. It is not a prefix of USA Minor Outlying
        Islands, and a two-letter code is never taken from the start of a longer
        name.
        """
        text = (raw or "").strip()
        if not text:
            return False
        token = _country_token(text)
        Country = self.env["res.country"]
        if token in _US_COUNTRY_ALIASES:
            country = Country.search([("code", "=", "US")], limit=1)
            return country.id if country else False
        if len(token) == 2 and token.isalpha():
            country = Country.search([("code", "=", token.upper())], limit=1)
            return country.id if country else False
        country = Country.search([("name", "=ilike", _collapse_ws(text))], limit=1)
        return country.id if country else False

    def _lead_vals_from_dto(self, dto: CanonicalLead) -> dict[str, Any]:
        # Lazy import mapping SSOT from crm_bridge
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import STAGE_MAPPING
        from odoo.addons.plasticos_facility_profile.models.lead_source import LEAD_SOURCE_MAPPING

        contact_name = " ".join(part for part in (_collapse_ws(dto.first_name), _collapse_ws(dto.last_name)) if part)
        company = (dto.company or "").strip()
        name = f"{company} — {contact_name}" if company and contact_name else (company or contact_name or "Unknown")

        stage_id = False
        xml_id = STAGE_MAPPING.get(dto.lead_status_raw)
        if xml_id:
            stage = self.env.ref(xml_id, raise_if_not_found=False)
            stage_id = stage.id if stage else False
        if not stage_id:
            stage = self.env.ref("plasticos_crm_bridge.stage_new", raise_if_not_found=False)
            stage_id = stage.id if stage else False

        source_id = False
        raw_source = (dto.lead_source_raw or "").strip()
        if raw_source and raw_source in LEAD_SOURCE_MAPPING:
            utm_name = LEAD_SOURCE_MAPPING[raw_source]
            source = self.env["utm.source"].search([("name", "=", utm_name)], limit=1)
            source_id = source.id if source else False

        country_id = self._resolve_country_id(dto.country_code)

        state_id = False
        if dto.state_code and country_id:
            state = self.env["res.country.state"].search(
                [("code", "=", dto.state_code.strip().upper()), ("country_id", "=", country_id)],
                limit=1,
            )
            state_id = state.id if state else False

        user_id = False
        owner_name = _collapse_ws(dto.owner_name)
        if owner_name and owner_name.casefold() != "false":
            users = self.env["res.users"].search([("name", "=ilike", owner_name)])
            user_id = users.id if len(users) == 1 else False

        return {
            "name": name,
            "type": "lead",
            "partner_name": company or False,
            "contact_name": contact_name or False,
            "email_from": dto.email or False,
            "phone": dto.phone or False,
            "mobile": dto.mobile or False,
            "street": dto.street or False,
            "street2": dto.street2 or False,
            "city": dto.city or False,
            "state_id": state_id,
            "zip": dto.zip or False,
            "country_id": country_id,
            "stage_id": stage_id,
            "source_id": source_id,
            "user_id": user_id,
            "vanillasoft_id": dto.external_id,
        }

    def _upsert_calls(self, connection, batch: list[CanonicalCall], run) -> int:
        """Upsert one call batch, classifying each row created|updated|unchanged|failed.

        Returns created+updated (the pinned counter contract). Classification
        is recorded into ``self.outcomes`` when the caller opened one.
        """
        outcomes = getattr(self, "outcomes", None)
        Call = self.env["plasticos.crm.call.event"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        Ref = self.env["plasticos.crm.external.ref"]
        created = 0
        updated = 0
        orphans = 0
        for dto in batch:
            existing = Call.search(
                [("provider", "=", dto.provider), ("external_id", "=", dto.external_id)],
                limit=1,
            )
            lead = self._find_lead(dto.provider, dto.contact_external_id, Ref)
            person_ref = self._find_person_ref(dto.provider, dto.contact_external_id)
            lead_id, partner_id = self._history_links(person_ref, lead)
            vals = {
                "provider": dto.provider,
                "external_id": dto.external_id,
                "contact_external_id": dto.contact_external_id,
                "call_datetime_utc": _dt_naive_utc(dto.call_datetime_utc),
                "duration_seconds": dto.duration_seconds,
                "user_name": dto.user_name or False,
                "result_code": dto.result_code or False,
                "comment": dto.comment or False,
                "lead_id": lead_id,
                "partner_id": partner_id,
            }
            try:
                if existing:
                    changed = {k: v for k, v in vals.items() if _differs(existing, k, v)}
                    if changed:
                        existing.write(changed)
                        updated += 1
                        if outcomes is not None:
                            outcomes["updated"] += 1
                    elif outcomes is not None:
                        outcomes["unchanged"] += 1
                elif not lead and not person_ref:
                    Orphan.create(
                        {
                            "connection_id": connection.id,
                            "provider": dto.provider,
                            "kind": "call",
                            "contact_external_id": dto.contact_external_id,
                            "external_id": dto.external_id,
                            "payload_json": {
                                "provider": dto.provider,
                                "external_id": dto.external_id,
                                "contact_external_id": dto.contact_external_id,
                                "call_datetime_utc": dto.call_datetime_utc,
                                "duration_seconds": dto.duration_seconds,
                                "user_name": dto.user_name,
                                "result_code": dto.result_code,
                                "comment": dto.comment,
                            },
                        }
                    )
                    orphans += 1
                    # Deferred: the orphan buffer is the no-loss mechanism,
                    # `orphans_buffered` persists the count, and the row is
                    # classified here so seen == sum(outcomes) holds. It is
                    # not created/updated/unchanged: nothing landed yet.
                    if outcomes is not None:
                        outcomes["deferred"] = outcomes.get("deferred", 0) + 1
                else:
                    Call.create(vals)
                    created += 1
                    if outcomes is not None:
                        outcomes["created"] += 1
            except Exception as exc:  # noqa: BLE001 - per-record failure is recorded, never silent loss
                self._record_outcome(outcomes, "failed", dto.external_id, str(exc))
        if run and orphans:
            run.orphans_buffered = (run.orphans_buffered or 0) + orphans
        return created + updated

    def _sync_tables_for_lead(self, connection, adapter, contact_external_id: str, lead=None):
        Ref = self.env["plasticos.crm.external.ref"]
        Row = self.env["plasticos.crm.external.table.row"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        outcomes = getattr(self, "outcomes", None)
        if lead is None:
            lead = self._find_lead(connection.provider, contact_external_id, Ref)
        person_ref = self._find_person_ref(connection.provider, contact_external_id)
        landed_fields = []
        for dto in adapter.iter_table_rows(contact_external_id):
            if not lead and not person_ref:
                Orphan.create(
                    {
                        "connection_id": connection.id,
                        "provider": dto.provider,
                        "kind": "table_row",
                        "contact_external_id": dto.contact_external_id,
                        "external_id": dto.external_row_id,
                        "payload_json": {
                            "provider": dto.provider,
                            "contact_external_id": dto.contact_external_id,
                            "table_id": dto.table_id,
                            "table_name": dto.table_name,
                            "external_row_id": dto.external_row_id,
                            "fields": dto.fields,
                        },
                    }
                )
                continue
            existing = Row.search(
                [
                    ("provider", "=", dto.provider),
                    ("table_id", "=", dto.table_id),
                    ("external_row_id", "=", dto.external_row_id),
                ],
                limit=1,
            )
            lead_id, partner_id = self._history_links(person_ref, lead)
            vals = {
                "provider": dto.provider,
                "lead_id": lead_id,
                "partner_id": partner_id,
                "contact_external_id": dto.contact_external_id,
                "table_id": dto.table_id,
                "table_name": dto.table_name or False,
                "external_row_id": dto.external_row_id,
                "fields_json": dto.fields,
            }
            if existing:
                changed = {k: v for k, v in vals.items() if _differs(existing, k, v)}
                if changed:
                    existing.write(changed)
                    if outcomes is not None:
                        outcomes["table_rows"] += 1
            else:
                Row.create(vals)
                if outcomes is not None:
                    outcomes["table_rows"] += 1
            landed_fields.append(dto.fields)
        if lead and landed_fields:
            if person_ref or self._approved_ct_id(contact_external_id):
                self._apply_approved_materials(lead, *landed_fields)
            else:
                self._apply_contact_materials(lead, *landed_fields)

    def _apply_contact_materials(self, lead, *field_maps) -> None:
        """Normalize each distinct material onto the lead's facility profile.

        A lead with no partner owns one facility profile and the material
        profiles on it. A lead that already has one resolvable facility partner
        keeps the partner-owned profiles. Manual sync and the scheduled cron
        both reach this through ``run_connection``. An unresolved material is
        reported and the contact is kept. Sync counters and watermarks are not
        changed.
        """
        try:
            with self.env.cr.savepoint():
                self._apply_resolved_materials(lead, *field_maps)
        except Exception as exc:  # noqa: BLE001 - material failure must not drop the admitted contact
            _logger.warning("Material normalization failed for lead %s: %s", lead.id, exc)
            self.error_rows.append(
                {"record_ref": str(lead.id or ""), "message": f"material normalization failed: {exc}"}
            )

    def _apply_resolved_materials(self, lead, *field_maps) -> None:
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            normalize_material,
        )
        from odoo.exceptions import ValidationError  # noqa: PLC0415

        phrases, hints, weak = _material_inputs(*field_maps)
        candidates = list(phrases)
        plain_hints = {}
        for label, value in hints.items():
            if normalize_material(self.env, value).polymer:
                candidates.append(value)
            else:
                plain_hints[label] = value
        texts = _dedupe_phrases(candidates) or list(weak)
        if not texts:
            return
        partner = None
        if lead.partner_id:
            partner, reason = _facility_for_material(lead)
            if partner is None:
                for text in texts:
                    self.error_rows.append(
                        {"record_ref": lead.vanillasoft_id or str(lead.id), "message": f"{reason}: {text}"}
                    )
                return
        owned = self.env["plasticos.facility.profile"].search([("crm_lead_id", "=", lead.id)], limit=1)
        if not owned and lead.facility_profile_id and lead.facility_profile_id.partner_id == partner:
            owned = lead.facility_profile_id
        if partner is not None and not owned:
            located = self.env["plasticos.facility.profile"].ensure_canonical_facility(partner, lead)
            self._store_normalized_materials(lead, texts, plain_hints, facility_profile=located)
            return
        if owned and partner is not None and owned.partner_id and owned.partner_id != partner:
            raise ValidationError("This lead is already associated with a different facility.")
        if owned and partner is not None and not owned.partner_id:
            owned = owned.link_verified_location(partner)
        elif not owned:
            owned = self.env["plasticos.facility.profile"].create({"crm_lead_id": lead.id})
        owned._remember_lead(lead)
        self._store_normalized_materials(lead, texts, plain_hints, facility_profile=owned)

    def _store_normalized_materials(self, lead, texts, plain_hints, partner=None, facility_profile=None) -> None:
        from odoo.addons.plasticos_material_profile.models.material_normalizer import (  # noqa: PLC0415
            normalize_material,
        )

        profiles = self.env["plasticos.material.profile"]
        for text in texts:
            normalized = normalize_material(self.env, text, structured=plain_hints)
            if normalized.unresolved or not normalized.polymer:
                detail = ", ".join(normalized.unresolved) or "unresolved material"
                self.error_rows.append(
                    {
                        "record_ref": lead.vanillasoft_id or str(lead.id),
                        "message": f"{detail}: {normalized.source_description}",
                    }
                )
                continue
            if partner is not None:
                profile = profiles.reuse_facility_polymer_profile(
                    partner,
                    normalized.polymer,
                    normalized.form,
                    note_line=normalized.source_description,
                )
            else:
                profile = profiles.reuse_lead_facility_material(
                    facility_profile,
                    normalized.polymer,
                    normalized.form,
                    note_line=normalized.source_description,
                )
            self._write_profile_classification(profile, normalized)

    def _write_profile_classification(self, profile, normalized) -> None:
        """Fill empty grade, source, and attributes. A second grade is not merged."""
        from odoo import Command  # noqa: PLC0415 - pure-Python tests import this module without Odoo

        if normalized.grade:
            current = (profile.sub_grade or "").strip()
            if current and current != normalized.grade:
                self.error_rows.append(
                    {
                        "record_ref": str(profile.id),
                        "message": (
                            f"grade {normalized.grade} conflicts with stored grade {current} "
                            f"on profile {profile.id}; attributes unchanged"
                        ),
                    }
                )
                return
            if not current:
                profile.sub_grade = normalized.grade
        if normalized.source_type and not profile.source_type_id:
            profile.source_type_id = normalized.source_type
        if not normalized.attributes:
            return
        missing = normalized.attributes - profile.material_attribute_ids
        if missing:
            profile.write({"material_attribute_ids": [Command.link(attribute.id) for attribute in missing]})

    def _resolve_orphans(self, connection, adapter, run) -> int:
        Orphan = self.env["plasticos.crm.sync.orphan"]
        Call = self.env["plasticos.crm.call.event"]
        Row = self.env["plasticos.crm.external.table.row"]
        Ref = self.env["plasticos.crm.external.ref"]
        orphans = Orphan.search(
            [
                ("connection_id", "=", connection.id),
                ("resolved", "=", False),
            ]
        )
        resolved = 0
        for orphan in orphans:
            lead = self._find_lead(orphan.provider, orphan.contact_external_id, Ref)
            person_ref = self._find_person_ref(orphan.provider, orphan.contact_external_id)
            if not lead and not person_ref:
                continue
            payload = orphan.payload_json or {}
            lead_id, partner_id = self._history_links(person_ref, lead)
            if orphan.kind == "call":
                existing = Call.search(
                    [
                        ("provider", "=", payload.get("provider")),
                        ("external_id", "=", payload.get("external_id")),
                    ],
                    limit=1,
                )
                vals = {
                    "provider": payload.get("provider"),
                    "external_id": payload.get("external_id"),
                    "contact_external_id": payload.get("contact_external_id"),
                    "call_datetime_utc": _dt_naive_utc(payload.get("call_datetime_utc")),
                    "duration_seconds": int(payload.get("duration_seconds") or 0),
                    "user_name": payload.get("user_name") or False,
                    "result_code": payload.get("result_code") or False,
                    "comment": payload.get("comment") or False,
                    "lead_id": lead_id,
                    "partner_id": partner_id,
                }
                if existing:
                    existing.write(vals)
                else:
                    Call.create(vals)
            elif orphan.kind == "table_row":
                existing = Row.search(
                    [
                        ("provider", "=", payload.get("provider")),
                        ("table_id", "=", payload.get("table_id")),
                        ("external_row_id", "=", payload.get("external_row_id")),
                    ],
                    limit=1,
                )
                vals = {
                    "provider": payload.get("provider"),
                    "lead_id": lead_id,
                    "partner_id": partner_id,
                    "contact_external_id": payload.get("contact_external_id"),
                    "table_id": payload.get("table_id"),
                    "table_name": payload.get("table_name") or False,
                    "external_row_id": payload.get("external_row_id"),
                    "fields_json": payload.get("fields") or {},
                }
                if existing:
                    existing.write(vals)
                else:
                    Row.create(vals)
            orphan.resolved = True
            resolved += 1
        if run:
            run.orphans_resolved = resolved
        return resolved

    def _history_links(self, person_ref, lead):
        """Return ``(lead_id, partner_id)`` for one call or custom-table row.

        A VanillaSoft contact bound to an ERP person keeps its history on that
        person. A contact that is still only a lead keeps its history on the lead.
        """
        if person_ref:
            return False, person_ref.res_id or False
        return (lead.id if lead else False), False

    def _find_lead(self, provider: str, contact_external_id: str, Ref):
        ref = Ref.search(
            [
                ("provider", "=", provider),
                ("external_id", "=", contact_external_id),
                ("res_model", "=", CRM_LEAD),
            ],
            limit=1,
        )
        if ref:
            lead = self.env[CRM_LEAD].browse(ref.res_id)
            if lead.exists():
                return lead
        # active_test=False for the same reason as `_upsert_lead`: a call or
        # custom-table row belonging to a sync-archived lead must attach to that
        # lead, not be buffered as an orphan that never resolves.
        return (
            self.env[CRM_LEAD]
            .with_context(active_test=False)
            .search([("vanillasoft_id", "=", contact_external_id)], limit=1)
        )
