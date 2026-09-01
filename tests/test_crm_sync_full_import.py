"""`run_full_import` — the manual VanillaSoft → Odoo bootstrap.

What is modelled here and what is not
-------------------------------------
These tests drive the REAL `run_full_import`, `_sync_contacts`, `_sync_calls`,
`_upsert_lead` and `_upsert_calls` against an in-memory ORM whose stores are
keyed exactly as the database's unique constraints are — `(provider,
external_id, res_model)` for the external ref, `(provider, external_id)` for the
call event. Identity, replay, watermark handoff, floor validation and phase
sequencing are therefore the production code paths, not stand-ins.

Two seams are replaced, both for the same reason the repo's existing
`_CountingOrchestrator` replaces them: they are not reachable without an Odoo
runtime and are not what these tests assert.

* `_lead_vals_from_dto` resolves stages, UTM sources, countries and users
  through `odoo.addons` imports.
* `_create_sync_run_durable` / `_persist_sync_failure_durable` /
  `_try_advisory_lock` open second cursors and take PostgreSQL session locks.

Real commit/rollback durability, row locks and cross-session visibility stay
real-runtime gates (docs/runbooks/LAUNCH_GATES.md), and the delete/restore
lifecycle is asserted against the real ORM in
`plasticos_crm_sync/tests/test_lead_lifecycle.py`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plasticos_crm_sync.adapters.base import (  # noqa: E402
    CanonicalCall,
    CanonicalLead,
    CanonicalTableRow,
    CrmAdapterError,
)
from plasticos_crm_sync.services.orchestrator import (  # noqa: E402
    CONTACT_LOOKBACK_MAX_DAYS,
    CrmFullImportArgumentError,
    SyncOrchestrator,
)

NOW = datetime.now(UTC)
# Comfortably outside the Contacts lookback, so the clamp the full import must
# not apply is the difference between reaching this contact and missing it.
ANCIENT = NOW - timedelta(days=900)
ANCIENT_Z = ANCIENT.strftime("%Y-%m-%dT%H:%M:%SZ")
RECENT_Z = (NOW - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
# Keeps a bootstrap call phase to one 1-day window; the contact floor is
# independent, so contact-census tests still reach back years.
CALL_FLOOR_Z = (NOW - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lead(external_id: str, modified: str = RECENT_Z, deleted: bool = False) -> CanonicalLead:
    return CanonicalLead(
        provider="vanillasoft",
        external_id=external_id,
        company=f"Co {external_id}",
        first_name="Ada",
        last_name="Lovelace",
        lead_status_raw="New",
        modified_utc=modified,
        deleted=deleted,
    )


def _call(external_id: str, contact_external_id: str = "c1") -> CanonicalCall:
    return CanonicalCall(
        provider="vanillasoft",
        external_id=external_id,
        contact_external_id=contact_external_id,
        call_datetime_utc=RECENT_Z,
        duration_seconds=30,
    )


# ── in-memory ORM ───────────────────────────────────────────────────────────


class _Record:
    def __init__(self, store, rec_id: int, vals: dict):
        self._store = store
        self.id = rec_id
        self.__dict__.update(vals)

    def __bool__(self):
        return True

    def write(self, vals):
        vals = dict(vals)
        for field in _Model.M2O & vals.keys():
            if isinstance(vals[field], int):
                vals[field] = _Id(vals[field])
        self.__dict__.update(vals)

    def exists(self):
        return self.id in self._store.rows


class _Missing:
    """Empty recordset — falsy, and `.id` is False as Odoo's is."""

    id = False

    def __bool__(self):
        return False

    def exists(self):
        return False

    def __getattr__(self, name):
        return False


MISSING = _Missing()


class _Id:
    """Odoo returns a recordset for a many2one; the orchestrator reads `.id`."""

    def __init__(self, value: int):
        self.id = value

    def __bool__(self):
        return bool(self.id)


class _Model:
    # Fields the orchestrator dereferences as `<field>.id`.
    M2O = frozenset({"lead_id", "connection_id"})

    def __init__(self, name: str, defaults: dict | None = None):
        self.name = name
        self.rows: dict[int, _Record] = {}
        self._next = 1
        self._defaults = defaults or {}
        self._active_test = True

    def with_context(self, **ctx):
        clone = object.__new__(_Model)
        clone.__dict__ = dict(self.__dict__)
        clone._active_test = ctx.get("active_test", self._active_test)
        return clone

    def browse(self, rec_id=None):
        if not rec_id:
            return MISSING
        return self.rows.get(rec_id, MISSING)

    def create(self, vals):
        rec_id = self._next
        self._next += 1
        merged = dict(self._defaults)
        merged.update(vals)
        for field in self.M2O & merged.keys():
            if isinstance(merged[field], int):
                merged[field] = _Id(merged[field])
        record = _Record(self, rec_id, merged)
        self.rows[rec_id] = record
        return record

    def search(self, domain, limit=None, order=None):
        matches = [r for r in self.rows.values() if self._matches(r, domain)]
        if self._active_test and "active" in self._defaults:
            matches = [r for r in matches if getattr(r, "active", True)]
        if limit == 1:
            return matches[0] if matches else MISSING
        return matches

    @staticmethod
    def _matches(record, domain) -> bool:
        for field, op, value in domain:
            assert op == "=", f"fake ORM supports only '='; got {op!r}"
            actual = getattr(record, field, None)
            if hasattr(actual, "id"):
                actual = actual.id
            if actual != value:
                return False
        return True


class _Cursor:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class _Env:
    def __init__(self):
        self.cr = _Cursor()
        self.uid = 1
        self.context = {}
        self.models = {
            "crm.lead": _Model("crm.lead", {"active": True, "vanillasoft_sync_archived": False}),
            "plasticos.crm.external.ref": _Model("plasticos.crm.external.ref"),
            "plasticos.crm.call.event": _Model("plasticos.crm.call.event"),
            "plasticos.crm.external.table.row": _Model("plasticos.crm.external.table.row"),
            "plasticos.crm.sync.orphan": _Model("plasticos.crm.sync.orphan", {"resolved": False}),
            "plasticos.crm.sync.run": _Model(
                "plasticos.crm.sync.run",
                {"contacts_upserted": 0, "calls_upserted": 0, "orphans_buffered": 0, "orphans_resolved": 0},
            ),
        }

    def __getitem__(self, name):
        return self.models[name]


class _Connection:
    id = 1
    provider = "vanillasoft"

    def __init__(self, contact_watermark=None, call_watermark=None):
        self.contact_watermark_utc = contact_watermark
        self.call_watermark_utc = call_watermark
        self.call_backfill_floor_utc = None
        self.last_error = False
        self.last_success_at = None

    def ensure_one(self):
        return self

    def write(self, vals):
        self.__dict__.update(vals)

    def default_contact_modified_after(self) -> str:
        if self.contact_watermark_utc:
            return self.contact_watermark_utc
        return _iso(datetime.now(UTC) - timedelta(days=30))


class _Adapter:
    """Records every bound it was asked for, per phase.

    `_sync_calls` slices its window into 1-day chunks and calls `iter_calls`
    once per chunk, so a phase is many `iter_calls` invocations. Scripted
    batches are therefore served once per PHASE (bootstrap, then catch-up),
    keyed off how many contact passes have started — not per invocation.
    """

    provider = "vanillasoft"
    live = True

    def __init__(self, contact_passes=(), call_passes=(), table_rows=()):
        self._contact_passes = list(contact_passes)
        self._call_passes = list(call_passes)
        self._table_rows = list(table_rows)
        self.contact_calls: list[str] = []
        self.call_windows: list[tuple[str, str]] = []
        # ("contacts", modified_after) / ("calls", start, end) in call order.
        self.timeline: list[tuple] = []
        self._phases_served: set[int] = set()

    @property
    def _phase(self) -> int:
        return max(len(self.contact_calls) - 1, 0)

    def healthcheck(self):
        return {}

    def iter_contacts(self, *, modified_after, limit=200):
        self.contact_calls.append(modified_after)
        self.timeline.append(("contacts", modified_after))
        index = len(self.contact_calls) - 1
        pages = self._contact_passes[index] if index < len(self._contact_passes) else []
        for page in pages:
            if isinstance(page, Exception):
                raise page
            yield page

    def iter_calls(self, *, start, end, limit=500):
        self.call_windows.append((start, end))
        self.timeline.append(("calls", start, end))
        phase = self._phase
        if phase in self._phases_served:
            return
        self._phases_served.add(phase)
        batches = self._call_passes[phase] if phase < len(self._call_passes) else []
        for batch in batches:
            if isinstance(batch, Exception):
                raise batch
            yield batch

    def iter_table_rows(self, contact_external_id):
        return iter(self._table_rows)


def _call_windows_by_phase(adapter) -> list[list[tuple[str, str]]]:
    """Split the recorded call windows at each contact pass."""
    phases: list[list[tuple[str, str]]] = []
    for entry in adapter.timeline:
        if entry[0] == "contacts":
            phases.append([])
        elif phases:
            phases[-1].append((entry[1], entry[2]))
    return phases


class _Orchestrator(SyncOrchestrator):
    """Real sync logic; only the Odoo-runtime-only seams are stubbed."""

    def __init__(self, env, adapter):
        super().__init__(env)
        self._adapter = adapter
        self.locked = 0

    def _build_adapter(self, connection):
        return self._adapter

    def _try_advisory_lock(self, lock_key):
        self.locked += 1
        return True

    def _advisory_unlock(self, lock_key):
        self.locked -= 1

    def _create_sync_run_durable(self, connection_id):
        return (
            self.env["plasticos.crm.sync.run"]
            .create({"connection_id": connection_id, "status": "running", "contacts_upserted": 0, "calls_upserted": 0})
            .id
        )

    def _persist_sync_failure_durable(self, connection_id, run_id, excerpt):
        run = self.env["plasticos.crm.sync.run"].browse(run_id)
        if run:
            run.write({"status": "failed", "error_excerpt": excerpt})

    def _lead_vals_from_dto(self, dto):
        # The real mapper resolves stages/sources/countries through
        # `odoo.addons` imports. Identity and lifecycle live in `_upsert_lead`,
        # which is NOT stubbed, so this returns only what a lead row needs.
        return {
            "name": dto.company or dto.external_id,
            "partner_name": dto.company or False,
            "email_from": dto.email or False,
            "vanillasoft_id": dto.external_id,
        }


def _harness(adapter, connection=None):
    env = _Env()
    return _Orchestrator(env, adapter), (connection or _Connection()), env


def _one_page(leads, batch_end):
    return [(leads, batch_end, False)]


# ── contact enumeration reaches past the rolling window ─────────────────────


def test_fresh_database_imports_a_contact_older_than_the_rolling_window():
    """The defect: `run_connection` clamps to 30 days, so an untouched contact
    from 2023 is unreachable however many times it runs."""
    adapter = _Adapter(
        contact_passes=[_one_page([_lead("old-1", modified=ANCIENT_Z)], ANCIENT_Z), []],
        call_passes=[[], []],
    )
    orch, connection, env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    assert adapter.contact_calls[0] == ANCIENT_Z, "bootstrap must ask for the operator's floor, unclamped"
    refs = env["plasticos.crm.external.ref"].search([("external_id", "=", "old-1")])
    assert len(refs) == 1
    assert env["crm.lead"].browse(refs[0].res_id).vanillasoft_id == "old-1"


def test_incremental_run_still_clamps_to_the_rolling_window():
    """Regression fence: the clamp removal is scoped to the full import."""
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z)])
    orch, connection, _env = _harness(adapter, _Connection(contact_watermark=ANCIENT_Z))
    orch._sync_contacts(connection, adapter, None)
    asked = datetime.fromisoformat(adapter.contact_calls[0].replace("Z", "+00:00"))
    assert asked > NOW - timedelta(days=31)


# ── explicit historical call floor ──────────────────────────────────────────


def test_full_import_processes_the_explicit_call_history_floor():
    floor = _iso(NOW - timedelta(days=3))
    adapter = _Adapter(
        contact_passes=[_one_page([_lead("c1")], RECENT_Z), []],
        call_passes=[[[_call("k1")]], []],
    )
    orch, connection, env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=floor)

    bootstrap = _call_windows_by_phase(adapter)[0]
    assert bootstrap[0][0] == floor, "historical calls must start at the operator's floor"
    # Contiguous 1-day windows from the floor to the catch-up boundary.
    assert [w[0] for w in bootstrap[1:]] == [w[1] for w in bootstrap[:-1]]
    assert len(env["plasticos.crm.call.event"].search([("external_id", "=", "k1")])) == 1


def test_full_import_does_not_substitute_the_short_default_history_window():
    """`_sync_calls` defaults to 7 days with no watermark; the full import must
    never silently fall back to it and then acknowledge the whole floor."""
    floor = _iso(NOW - timedelta(days=20))
    adapter = _Adapter(contact_passes=[[], []], call_passes=[[], []])
    orch, connection, _env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=floor)
    first_start = datetime.fromisoformat(_call_windows_by_phase(adapter)[0][0][0].replace("Z", "+00:00"))
    assert first_start < NOW - timedelta(days=15)


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_a_missing_call_history_floor_names_the_parameter(missing):
    """A blank floor is refused as *required*, not as an unparseable date — the
    operator has to be told which bound to supply."""
    orch, connection, _env = _harness(_Adapter())
    with pytest.raises(CrmFullImportArgumentError, match="call_history_floor is required"):
        orch.run_full_import(connection, call_history_floor=missing)


@pytest.mark.parametrize("bad", [None, "", "   ", "not-a-date", "2026-13-45T00:00:00Z"])
def test_invalid_call_history_floor_fails_closed(bad):
    adapter = _Adapter(contact_passes=[[]], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    with pytest.raises(CrmFullImportArgumentError):
        orch.run_full_import(connection, call_history_floor=bad)
    # Nothing started: no lock held, no audit row, no remote call, no watermark.
    assert orch.locked == 0
    assert env["plasticos.crm.sync.run"].rows == {}
    assert adapter.contact_calls == [] and adapter.call_windows == []
    assert connection.contact_watermark_utc is None and connection.call_watermark_utc is None


def test_a_future_call_history_floor_fails_closed():
    adapter = _Adapter()
    orch, connection, _env = _harness(adapter)
    with pytest.raises(CrmFullImportArgumentError, match="future"):
        orch.run_full_import(connection, call_history_floor=_iso(NOW + timedelta(days=1)))


# ── bootstrap / catch-up seam ───────────────────────────────────────────────


def test_bootstrap_catchup_does_not_miss_a_contact_modified_during_the_import():
    """`during-1` does not exist on the bootstrap pass and appears only on the
    catch-up pass — exactly the race the boundary + second pass exist for."""
    adapter = _Adapter(
        contact_passes=[
            _one_page([_lead("before-1", modified=ANCIENT_Z)], ANCIENT_Z),
            _one_page([_lead("during-1", modified=RECENT_Z)], RECENT_Z),
        ],
        call_passes=[[], []],
    )
    orch, connection, env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    ids = {r.external_id for r in env["plasticos.crm.external.ref"].search([])}
    assert ids == {"before-1", "during-1"}


def test_the_catchup_call_window_overlaps_the_bootstrap_boundary():
    """Abutting windows leak a call written in the seam between them."""
    adapter = _Adapter(contact_passes=[[], []], call_passes=[[], []])
    orch, connection, _env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z)

    bootstrap, catchup = _call_windows_by_phase(adapter)
    bootstrap_end = datetime.fromisoformat(bootstrap[-1][1].replace("Z", "+00:00"))
    catchup_start = datetime.fromisoformat(catchup[0][0].replace("Z", "+00:00"))
    assert catchup_start < bootstrap_end


# ── watermark handoff and replay ────────────────────────────────────────────


def test_successful_full_import_leaves_valid_forward_watermarks():
    adapter = _Adapter(
        contact_passes=[_one_page([_lead("c1", modified=ANCIENT_Z)], ANCIENT_Z), _one_page([_lead("c1")], RECENT_Z)],
        call_passes=[[], []],
    )
    orch, connection, _env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    assert connection.contact_watermark_utc == RECENT_Z
    call_wm = datetime.fromisoformat(connection.call_watermark_utc.replace("Z", "+00:00"))
    assert call_wm > NOW - timedelta(minutes=10), "the next incremental run must resume at the boundary, not the floor"


def test_full_import_then_incremental_replay_creates_no_duplicate_leads():
    pages = _one_page([_lead("c1", modified=ANCIENT_Z), _lead("c2", modified=ANCIENT_Z)], ANCIENT_Z)
    adapter = _Adapter(contact_passes=[pages, pages], call_passes=[[], []])
    orch, connection, env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    # The incremental path immediately afterwards, re-reading the same page.
    replay = _Adapter(contact_passes=[pages])
    orch._sync_contacts(connection, replay, None)

    assert len(env["plasticos.crm.external.ref"].search([])) == 2
    assert len(env["crm.lead"].rows) == 2


def test_full_import_then_incremental_replay_creates_no_duplicate_calls():
    batch = [[_call("k1"), _call("k2")]]
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z), []], call_passes=[batch, batch])
    orch, connection, env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z)

    orch._upsert_calls(connection, [_call("k1"), _call("k2")], None)
    assert len(env["plasticos.crm.call.event"].search([])) == 2


def test_full_import_does_not_rewind_an_already_newer_watermark():
    """Re-running the bootstrap on a synced database must not reset months of
    acknowledged incremental progress back to the historical floor."""
    adapter = _Adapter(
        contact_passes=[_one_page([_lead("c1", modified=ANCIENT_Z)], ANCIENT_Z), []],
        call_passes=[[], []],
    )
    ahead = _iso(NOW - timedelta(hours=1))
    orch, connection, _env = _harness(adapter, _Connection(contact_watermark=ahead, call_watermark=ahead))
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    assert connection.contact_watermark_utc == ahead
    assert datetime.fromisoformat(connection.call_watermark_utc.replace("Z", "+00:00")) >= NOW - timedelta(hours=1)


# ── census completeness is verified, never assumed ──────────────────────────


def test_an_unproven_census_is_reported_partial_not_success():
    """Every returned contact was modified inside the lookback, so nothing
    proves the provider honoured the older floor rather than clamping it."""
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1", modified=RECENT_Z)], RECENT_Z), []], call_passes=[[], []])
    orch, connection, env = _harness(adapter)
    run = orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    assert env["plasticos.crm.sync.run"].browse(run.id).status == "partial"
    assert "Contact census unproven" in connection.last_error


def test_a_contact_older_than_the_lookback_proves_the_census():
    old = _iso(NOW - timedelta(days=CONTACT_LOOKBACK_MAX_DAYS + 60))
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1", modified=old)], old), []], call_passes=[[], []])
    orch, connection, env = _harness(adapter)
    run = orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    assert env["plasticos.crm.sync.run"].browse(run.id).status == "success"
    assert connection.last_error is False


def test_a_floor_inside_the_lookback_has_nothing_to_prove():
    inside = _iso(NOW - timedelta(days=5))
    adapter = _Adapter(contact_passes=[_one_page([_lead("c1")], RECENT_Z), []], call_passes=[[], []])
    orch, connection, env = _harness(adapter)
    run = orch.run_full_import(connection, call_history_floor=inside)
    assert env["plasticos.crm.sync.run"].browse(run.id).status == "success"


# ── failure handling ────────────────────────────────────────────────────────


def test_a_failed_bootstrap_page_leaves_the_watermark_untouched_and_releases_the_lock():
    adapter = _Adapter(contact_passes=[[CrmAdapterError("source down")]], call_passes=[[]])
    orch, connection, env = _harness(adapter)
    with pytest.raises(CrmAdapterError):
        orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)

    assert connection.contact_watermark_utc is None
    assert orch.locked == 0
    assert env["plasticos.crm.sync.run"].browse(1).status == "failed"


def test_counters_accumulate_across_bootstrap_and_catchup():
    adapter = _Adapter(
        contact_passes=[
            _one_page([_lead(f"a{i}", modified=ANCIENT_Z) for i in range(4)], ANCIENT_Z),
            _one_page([_lead(f"b{i}") for i in range(3)], RECENT_Z),
        ],
        call_passes=[[[_call("k1", "a0"), _call("k2", "a0")]], [[_call("k3", "a0")]]],
    )
    orch, connection, env = _harness(adapter)
    run = env["plasticos.crm.sync.run"].browse(
        orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z).id
    )
    assert run.contacts_upserted == 7
    assert run.calls_upserted == 3


def test_table_rows_are_attached_during_the_bootstrap():
    row = CanonicalTableRow(
        provider="vanillasoft",
        contact_external_id="c1",
        table_id="7",
        table_name="Grades",
        external_row_id="row-9",
        fields={"grade": "HDPE"},
    )
    adapter = _Adapter(
        contact_passes=[_one_page([_lead("c1", modified=ANCIENT_Z)], ANCIENT_Z), []],
        call_passes=[[], []],
        table_rows=[row],
    )
    orch, connection, env = _harness(adapter)
    orch.run_full_import(connection, call_history_floor=CALL_FLOOR_Z, contact_modified_floor=ANCIENT_Z)
    assert len(env["plasticos.crm.external.table.row"].search([("external_row_id", "=", "row-9")])) == 1


# ── delete / restore provenance ─────────────────────────────────────────────
#
# Asserted against the real ORM in
# `plasticos_crm_sync/tests/test_lead_lifecycle.py`; repeated here so the
# behaviour is also covered by the tier that runs without an Odoo runtime. The
# fake `crm.lead` model applies the same `active_test` filter Odoo does.


def _drop_ref(env, external_id):
    """Force the `vanillasoft_id` fallback — the path that misses archived
    leads without `active_test=False`, and duplicates them as a result."""
    refs = env["plasticos.crm.external.ref"].search([("external_id", "=", external_id)])
    for ref in refs:
        del env["plasticos.crm.external.ref"].rows[ref.id]


def test_a_deleted_contact_archives_the_lead_and_records_the_provenance():
    orch, connection, env = _harness(_Adapter())
    orch._upsert_lead(connection, _lead("d1"))
    lead = orch._upsert_lead(connection, _lead("d1", deleted=True))
    assert lead.active is False
    assert lead.vanillasoft_sync_archived is True


def test_a_restored_contact_reactivates_a_sync_archived_lead():
    orch, connection, env = _harness(_Adapter())
    created = orch._upsert_lead(connection, _lead("d2"))
    orch._upsert_lead(connection, _lead("d2", deleted=True))
    restored = orch._upsert_lead(connection, _lead("d2"))
    assert restored.id == created.id
    assert restored.active is True
    assert restored.vanillasoft_sync_archived is False


def test_a_manually_archived_lead_is_not_reactivated_without_sync_provenance():
    """`deleted=false` is the provider's steady state for every live contact —
    mirroring it onto `active` would reopen every lead a user ever archived."""
    orch, connection, env = _harness(_Adapter())
    lead = orch._upsert_lead(connection, _lead("d3"))
    lead.write({"active": False})  # an Odoo user archived it
    assert lead.vanillasoft_sync_archived is False

    orch._upsert_lead(connection, _lead("d3"))
    assert lead.active is False


def test_a_sync_archived_lead_is_matched_by_the_fallback_not_duplicated():
    orch, connection, env = _harness(_Adapter())
    first = orch._upsert_lead(connection, _lead("d4"))
    orch._upsert_lead(connection, _lead("d4", deleted=True))
    _drop_ref(env, "d4")

    again = orch._upsert_lead(connection, _lead("d4"))
    assert again.id == first.id
    assert len(env["crm.lead"].rows) == 1


def test_calls_attach_to_a_sync_archived_lead_instead_of_buffering_as_orphans():
    orch, connection, env = _harness(_Adapter())
    lead = orch._upsert_lead(connection, _lead("d5"))
    orch._upsert_lead(connection, _lead("d5", deleted=True))
    _drop_ref(env, "d5")

    orch._upsert_calls(connection, [_call("d5-call", "d5")], None)
    events = env["plasticos.crm.call.event"].search([("external_id", "=", "d5-call")])
    assert len(events) == 1
    assert events[0].lead_id.id == lead.id
    assert env["plasticos.crm.sync.orphan"].search([("external_id", "=", "d5-call")]) == []
