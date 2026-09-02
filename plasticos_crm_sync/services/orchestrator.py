"""CRM sync orchestrator — DTO → ORM write path with watermarks and orphans."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from ..adapters.base import CanonicalCall, CanonicalLead, CrmAdapterError, CrmAdapterStubError
from ..adapters.registry import ensure_live_or_raise, get_adapter

_logger = logging.getLogger(__name__)

CRM_LEAD = "crm.lead"
CONTACT_PAGE_SIZE = 200
CALL_BATCH_SIZE = 500

# The Contacts list endpoint accepts `modified_after` only within this lookback
# (docs/runbooks/CRM_SYNC_VANILLASOFT.md). Incremental runs clamp to it; the
# full import deliberately does not, and instead verifies at runtime that the
# older floor it asked for was actually honoured — see `run_full_import`.
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


class SyncOrchestrator:
    def __init__(self, env):
        self.env = env
        # Reset by every `_sync_contacts` pass; read by `run_full_import` as the
        # evidence that the requested historical floor was actually served.
        self.oldest_contact_modified_seen: datetime | None = None

    def run_connection(self, connection) -> Any:
        connection.ensure_one()
        connection_id = connection.id
        # I17 — every durable row this method creates lives on a cursor of its
        # own (`_create_sync_run_durable`), and `plasticos_crm_sync_run` carries
        # a foreign key to this connection. PostgreSQL cannot see a row the
        # caller's transaction has not committed, so a connection created by the
        # caller and handed straight here makes that INSERT fail the FK — the
        # first-run Settings path, where the operator's very first sync creates
        # the connection and syncs it in one RPC.
        #
        # `flush()` cannot fix this: it writes the INSERT inside the caller's
        # transaction, where a second connection still cannot read it. Only a
        # commit makes the row visible to a transaction this process does not
        # own. `Cursor.commit()` flushes first, so the pending INSERT lands.
        #
        # The boundary belongs here rather than in each caller: this is the
        # method that opens the independent cursor, so it is the method that
        # owns the precondition. Callers that reach this point have finished the
        # work they wanted durable — the Settings action has already run
        # `set_values()`, and the cron holds nothing pending.
        self.env.cr.commit()
        # I5 — session advisory lock at the single choke point, so the cron and
        # the manual `action_sync_now` button exclude each other. Session locks
        # survive the page commits below (they are not transaction-scoped) and
        # are re-entrant within one backend session, so the cron's own outer
        # lock nests harmlessly.
        lock_key = advisory_lock_key(connection_id)
        if not self._try_advisory_lock(lock_key):
            raise CrmSyncLockedError(f"CRM sync already running for connection {connection_id}")
        try:
            # I2 — the audit record must exist independently of the fallible
            # remote work it describes, so create it on an owned cursor that
            # commits before the first adapter call.
            run_id = self._create_sync_run_durable(connection_id)
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
                ensure_live_or_raise(adapter)
                adapter.healthcheck()
                contacts_n = self._sync_contacts(connection, adapter, run)
                calls_n = self._sync_calls(connection, adapter, run)
                resolved = self._resolve_orphans(connection, adapter, run)
                run.write(
                    {
                        "status": "success",
                        "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        "contacts_upserted": contacts_n,
                        "calls_upserted": calls_n,
                        "orphans_resolved": resolved,
                    }
                )
                connection.write(
                    {
                        "last_error": False,
                        "last_success_at": datetime.now(UTC).replace(tzinfo=None),
                    }
                )
                # Land this connection's outcome before the caller (cron) moves
                # to the next one: a later connection's rollback must not erase
                # a successful run that already happened.
                self.env.cr.commit()
            except (CrmAdapterStubError, CrmAdapterError, Exception) as exc:
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
            # owned cursor before the first fallible remote call.
            run_id = self._create_sync_run_durable(connection_id)
            self.env.cr.commit()
            run = self.env["plasticos.crm.sync.run"].browse(run_id)
            try:
                adapter = self._build_adapter(connection)
                ensure_live_or_raise(adapter)
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
                )
                catchup_calls = self._sync_calls(
                    connection,
                    adapter,
                    run,
                    start_override=boundary - CATCHUP_OVERLAP,
                    counter_base=bootstrap_calls,
                )
                resolved = self._resolve_orphans(connection, adapter, run)

                run.write(
                    {
                        "status": "partial" if gap else "success",
                        "finished_at": datetime.now(UTC).replace(tzinfo=None),
                        "contacts_upserted": bootstrap_contacts + catchup_contacts,
                        "calls_upserted": bootstrap_calls + catchup_calls,
                        "orphans_resolved": resolved,
                        "error_excerpt": gap or False,
                    }
                )
                connection.write(
                    {
                        "last_error": gap or False,
                        "last_success_at": datetime.now(UTC).replace(tzinfo=None),
                    }
                )
                self.env.cr.commit()
                _logger.info(
                    "CRM full import connection=%s contacts=%s calls=%s status=%s "
                    "contact_floor=%s call_floor=%s boundary=%s oldest_contact_modified=%s",
                    connection_id,
                    bootstrap_contacts + catchup_contacts,
                    bootstrap_calls + catchup_calls,
                    "partial" if gap else "success",
                    contact_floor,
                    _iso_z(call_floor),
                    _iso_z(boundary),
                    _iso_z(oldest_seen) if oldest_seen else "none",
                )
            except (CrmAdapterStubError, CrmAdapterError, Exception) as exc:
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

        The list endpoint documents a 31-day maximum on `modified_after`
        (docs/runbooks/CRM_SYNC_VANILLASOFT.md). The full import asks for an
        older floor anyway, because the two failure modes differ sharply:

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

    def _try_advisory_lock(self, lock_key: str) -> bool:
        self.env.cr.execute("SELECT pg_try_advisory_lock(hashtext(%s))", [lock_key])
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    def _advisory_unlock(self, lock_key: str) -> None:
        self.env.cr.execute("SELECT pg_advisory_unlock(hashtext(%s))", [lock_key])

    def _create_sync_run_durable(self, connection_id: int) -> int:
        """Create the sync-run audit row on an owned cursor and commit it.

        Committing the ambient RPC cursor is unsafe (Odoo owns it), so the
        durable audit state gets its own transaction. Returns the primitive id.
        """
        from odoo import api

        with self.env.registry.cursor() as cr:
            env = api.Environment(cr, self.env.uid, dict(self.env.context))
            run = env["plasticos.crm.sync.run"].create(
                {
                    "connection_id": connection_id,
                    "status": "running",
                    "started_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
            run_id = run.id
            cr.commit()
        return run_id

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
        ensure_live_or_raise(adapter)
        lead_dto = adapter.get_contact(str(external_id))
        if not lead_dto:
            raise CrmAdapterError(f"Contact {external_id} not found")
        lead = self._upsert_lead(connection, lead_dto)
        calls_n = 0
        if hasattr(adapter, "iter_calls_for_contact"):
            for batch in adapter.iter_calls_for_contact(str(external_id)):
                calls_n += self._upsert_calls(connection, batch, None)
        self._sync_tables_for_lead(connection, adapter, lead_dto.external_id, lead)
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
    ) -> int:
        if modified_after_override:
            # Full import: the operator named this floor explicitly, so the
            # rolling clamp below must not silently shorten it back to 30 days.
            # `oldest_contact_modified_seen` is what proves afterwards whether
            # the provider honoured it (see `run_full_import`).
            modified_after = modified_after_override
        else:
            modified_after = connection.default_contact_modified_after()
            # Clamp to 31-day API max
            floor = datetime.now(UTC) - timedelta(days=INCREMENTAL_CONTACT_LOOKBACK_DAYS)
            parsed = _parse_utc(modified_after)
            if parsed and parsed < floor:
                modified_after = _iso_z(floor)
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
        last_batch_end = None
        for leads, batch_end, _partial in adapter.iter_contacts(
            modified_after=modified_after,
            limit=CONTACT_PAGE_SIZE,
        ):
            page_n = 0
            for dto in leads:
                lead = self._upsert_lead(connection, dto)
                if not dto.deleted:
                    self._sync_tables_for_lead(connection, adapter, dto.external_id, lead)
                self._observe_contact_modified(dto)
                page_n += 1
            pending += page_n
            if batch_end:
                last_batch_end = batch_end
                forward = _forward_only(connection.contact_watermark_utc, batch_end)
                if forward:
                    connection.contact_watermark_utc = forward
                if run:
                    run.contacts_upserted = counter_base + committed + pending
                self.env.cr.commit()  # records + watermark + counter, one page
                committed += pending
                pending = 0
        if last_batch_end:
            forward = _forward_only(connection.contact_watermark_utc, last_batch_end)
            if forward:
                connection.contact_watermark_utc = forward
        if run:
            # Any trailing `pending` is committed by run_connection's success
            # commit; on the failure path this write is rolled back with it.
            run.contacts_upserted = counter_base + committed + pending
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
    ) -> int:
        now = datetime.now(UTC)
        end = end_override or now
        if start_override is not None:
            # Full import: an explicit, already-validated historical floor. The
            # short rolling defaults below must not silently replace it.
            start = start_override
        elif connection.call_watermark_utc:
            start = _parse_utc(connection.call_watermark_utc) or (now - timedelta(days=7))
        elif connection.call_backfill_floor_utc:
            start = _parse_utc(connection.call_backfill_floor_utc) or (now - timedelta(days=30))
        else:
            start = now - timedelta(days=7)

        # Window size: 1 day chunks to keep batches manageable
        # Same committed-vs-attempted split as _sync_contacts: the counter is
        # written into the batch transaction, and `committed` advances only
        # after that commit returns.
        committed = 0
        cursor = start
        while cursor < end:
            window_end = min(cursor + timedelta(days=1), end)
            for batch in adapter.iter_calls(
                start=_iso_z(cursor),
                end=_iso_z(window_end),
                limit=CALL_BATCH_SIZE,
            ):
                batch_n = self._upsert_calls(connection, batch, run)
                if run:
                    run.calls_upserted = counter_base + committed + batch_n
                self.env.cr.commit()  # batch commit
                committed += batch_n
            forward = _forward_only(connection.call_watermark_utc, _iso_z(window_end))
            if forward:
                connection.call_watermark_utc = forward
            self.env.cr.commit()  # watermark advance
            cursor = window_end
        if run:
            run.calls_upserted = counter_base + committed
        return committed

    def _upsert_lead(self, connection, dto: CanonicalLead):
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

        if lead:
            lead.write(vals)
        else:
            lead = Lead.create(vals)

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
        elif ref.res_id != lead.id or ref.lead_id.id != lead.id:
            ref.write({"res_id": lead.id, "lead_id": lead.id})
        return lead

    def _lead_vals_from_dto(self, dto: CanonicalLead) -> dict[str, Any]:
        # Lazy import mapping SSOT from crm_bridge
        from odoo.addons.plasticos_crm_bridge.models.crm_mapping import STAGE_MAPPING
        from odoo.addons.plasticos_facility_profile.models.lead_source import LEAD_SOURCE_MAPPING

        contact_name = " ".join(filter(None, [dto.first_name, dto.last_name])).strip()
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
        if dto.lead_source_raw:
            utm_name = LEAD_SOURCE_MAPPING.get(dto.lead_source_raw.strip(), "Other")
            source = self.env["utm.source"].search([("name", "=", utm_name)], limit=1)
            source_id = source.id if source else False

        country_id = False
        if dto.country_code:
            country = self.env["res.country"].search(
                [
                    "|",
                    ("code", "=", dto.country_code.strip().upper()[:2]),
                    ("name", "ilike", dto.country_code.strip()),
                ],
                limit=1,
            )
            country_id = country.id if country else False

        state_id = False
        if dto.state_code:
            domain = [("code", "=", dto.state_code.strip().upper())]
            if country_id:
                domain.append(("country_id", "=", country_id))
            state = self.env["res.country.state"].search(domain, limit=1)
            state_id = state.id if state else False

        user_id = False
        if dto.owner_name and dto.owner_name.strip() not in ("FALSE", ""):
            user = self.env["res.users"].search([("name", "ilike", dto.owner_name.strip())], limit=1)
            user_id = user.id if user else False

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
        Call = self.env["plasticos.crm.call.event"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
        Ref = self.env["plasticos.crm.external.ref"]
        created = 0
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
            if existing:
                existing.write(vals)
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
            else:
                Call.create(vals)
                created += 1
        if run and orphans:
            run.orphans_buffered = (run.orphans_buffered or 0) + orphans
        return created

    def _sync_tables_for_lead(self, connection, adapter, contact_external_id: str, lead=None):
        Ref = self.env["plasticos.crm.external.ref"]
        Row = self.env["plasticos.crm.external.table.row"]
        Orphan = self.env["plasticos.crm.sync.orphan"]
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
                existing.write(vals)
            else:
                Row.create(vals)

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
