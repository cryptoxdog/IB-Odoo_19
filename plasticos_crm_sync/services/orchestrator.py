"""CRM sync orchestrator — DTO → ORM write path with watermarks and orphans."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ..adapters.base import CanonicalCall, CanonicalLead, CrmAdapterError
from ..adapters.registry import get_adapter

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
        adapter = self._build_adapter(connection)
        lead_dto = adapter.get_contact(str(external_id))
        if not lead_dto:
            raise CrmAdapterError(f"Contact {external_id} not found")
        lead = self._upsert_lead(connection, lead_dto)
        calls_n = 0
        if self.last_lead_outcome in ADMITTED_OUTCOMES:
            if hasattr(adapter, "iter_calls_for_contact"):
                for batch in adapter.iter_calls_for_contact(str(external_id)):
                    calls_n += self._upsert_calls(connection, batch, None)
            self._sync_tables_for_lead(connection, adapter, lead_dto.external_id, lead)
        else:
            # Identity conflict or write failure: no dependent writes may hang
            # off an unadmitted lead (they would attach to an arbitrary match).
            _logger.warning(
                "Single-contact sync skipped dependent writes external_id=%s outcome=%s",
                external_id,
                self.last_lead_outcome,
            )
        self._resolve_orphans(connection, adapter, None)
        _logger.info(
            "Single-contact sync done external_id=%s lead_id=%s calls=%s",
            external_id,
            lead.id,
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
                lead = self._upsert_lead(connection, dto)
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

    def _upsert_lead(self, connection, dto: CanonicalLead):
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
        return lead

    def _record_outcome(self, outcomes: dict[str, int] | None, outcome: str, record_ref: str, message: str) -> None:
        """Record a classified outcome + error detail (duplicate/failed rows)."""
        if outcomes is None:
            return
        outcomes[outcome] += 1
        self.error_rows.append({"record_ref": record_ref, "message": message})

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
            vals = {
                "provider": dto.provider,
                "external_id": dto.external_id,
                "contact_external_id": dto.contact_external_id,
                "call_datetime_utc": _dt_naive_utc(dto.call_datetime_utc),
                "duration_seconds": dto.duration_seconds,
                "user_name": dto.user_name or False,
                "result_code": dto.result_code or False,
                "comment": dto.comment or False,
                "lead_id": lead.id if lead else False,
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
                elif not lead:
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
        for dto in adapter.iter_table_rows(contact_external_id):
            if not lead:
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
            vals = {
                "provider": dto.provider,
                "lead_id": lead.id,
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
            if not lead:
                continue
            payload = orphan.payload_json or {}
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
                    "lead_id": lead.id,
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
                    "lead_id": lead.id,
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
